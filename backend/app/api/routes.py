from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from app.api.dependencies import (
    _get_user_repository,
    extract_bearer_token,
    get_current_user,
    get_ai_user,
    get_app_settings,
    require_role,
)
from app.api.schemas import (
    AbbreviationResponse,
    DictionarySyncResponse,
    AddAbbreviationMeaningRequest,
    AbbreviationUpsertRequest,
    AssignRoleRequest,
    AuthLoginRequest,
    DiacriticRestoreRequest,
    DiacriticRestoreResponse,
    DisambiguateRequest,
    DisambiguateResponse,
    HistoryCreateRequest,
    HistoryEntryResponse,
    AuthLogoutRequest,
    AuthRegisterRequest,
    AuthResponse,
    LiveNormalizeRequest,
    LiveNormalizeResponse,
    NormalizeRequest,
    NormalizeResponse,
    PendingAbbreviationResponse,
    PendingApprovalRequest,
    PendingRejectionRequest,
    PhraseOverrideCreateRequest,
    PhraseOverrideUpdateRequest,
    PreferenceSetRequest,
    UserAbbreviationMeaningRequest,
    UserResponse,
)
from app.auth.service import AuthService
from app.bootstrap import build_pipeline
from app.config import Settings, get_settings
from app.data_manager.db import health_check
from app.data_manager.history_repo import HistoryRepository
from app.data_manager.new_tables_repo import UsageStatsRepository
from app.data_manager.pending_service import PendingAbbreviationService
from app.data_manager.user_repo import UserRepository
from app.ai.client import NullClient, build_default_client
from app.ai.disambiguator import AmbiguityInput
from app.ai.errors import AIError
from app.ai.services import get_disambiguator, get_semantic_verifier
from app.normalizer.diacritic_restorer import (
    DiacriticRestorer,
    SyncDiacriticRestorer,
    get_shared_context_phrase_overrides,
    get_shared_bigram_freq,
    get_shared_word_map,
)
from app.normalizer.live_normalizer import LiveNormalizerService

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, Request
    from fastapi.concurrency import run_in_threadpool
except ImportError:  # pragma: no cover - API layer is optional in this phase
    APIRouter = None  # type: ignore[assignment]
    Depends = None  # type: ignore[assignment]
    HTTPException = RuntimeError  # type: ignore[assignment]
    Query = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]
    run_in_threadpool = None  # type: ignore[assignment]

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
except ImportError:  # pragma: no cover - dev environments without slowapi
    Limiter = None  # type: ignore[assignment]
    get_remote_address = None  # type: ignore[assignment]


def _rate_limit_key(request) -> str:
    """Prefer authenticated user when present; fall back to client IP."""
    user = getattr(getattr(request, "state", None), "user", None)
    if isinstance(user, dict) and user.get("id"):
        return f"user:{user['id']}"
    if get_remote_address is not None:
        return get_remote_address(request)
    return "anonymous"


def _load_diacritic_assets(data_dir):
    """Load the shared diacritic indexes as one threadpool-bound operation."""
    return (
        get_shared_word_map(data_dir),
        get_shared_bigram_freq(data_dir),
        get_shared_context_phrase_overrides(data_dir),
    )


_settings_for_limiter = get_settings()
limiter = (
    Limiter(key_func=_rate_limit_key, enabled=_settings_for_limiter.rate_limit_enabled)
    if Limiter is not None
    else None
)


def _limit(rule: str):
    """Apply a slowapi limit if slowapi is installed; otherwise no-op."""
    if limiter is None:

        def _identity(func):
            return func

        return _identity
    return limiter.limit(rule)


router = APIRouter() if APIRouter else None
_SEMANTIC_TYPING_ENDINGS = {".", "?", "!", "\u2026"}


_HEALTH_CACHE_TTL_SECONDS = 5.0
_health_cache: dict[int, tuple[bool, float]] = {}
_health_cache_lock = threading.Lock()


def _cached_health(settings: Settings) -> bool:
    """Short-lived cache for the DB probe.

    /api/health is unauthenticated, so an uncached handler let anyone open a new
    SQL Server connection per request — a cheap way to exhaust the pool.
    """
    key = id(settings)
    now = time.monotonic()
    with _health_cache_lock:
        cached = _health_cache.get(key)
        if cached and cached[1] > now:
            return cached[0]
    ok, _message = health_check(settings)
    with _health_cache_lock:
        _health_cache[key] = (ok, time.monotonic() + _HEALTH_CACHE_TTL_SECONDS)
    return ok


def _require_ready(service: PendingAbbreviationService) -> None:
    if not service.db_is_ready():
        raise HTTPException(status_code=503, detail="SQL Server chua san sang")


def _has_semantic_verification_signal(result: object, settings: Settings) -> bool:
    ambiguities = getattr(result, "ambiguities", [])
    if ambiguities:
        return True

    diacritic_changes = getattr(result, "diacritic_changes", [])
    return bool(
        getattr(result, "diacritic_applied", False)
        and bool(diacritic_changes)
    )


def _should_apply_semantic_verification(
    input_method: str,
    text: str,
    result: object,
    settings: Settings,
) -> bool:
    return (input_method in {"typing", "paste"} and bool(text.strip())
            and settings.semantic_verify_enabled)


def _get_pending_service(
    settings: Settings = Depends(get_app_settings),
) -> PendingAbbreviationService:
    return PendingAbbreviationService(settings)


def _get_auth_service(settings: Settings = Depends(get_app_settings)) -> AuthService:
    return AuthService(settings)


def _get_history_repository(settings: Settings = Depends(get_app_settings)) -> HistoryRepository:
    return HistoryRepository(settings)


if router:

    @router.post("/api/auth/register", response_model=AuthResponse)
    @_limit(_settings_for_limiter.rate_limit_register)
    def register(
        request: Request,
        payload: AuthRegisterRequest,
        auth_service: AuthService = Depends(_get_auth_service),
    ):
        result = auth_service.register(payload.username, payload.email, payload.password)
        if result["status"] == "INVALID_INPUT":
            raise HTTPException(status_code=400, detail="Thong tin dang ky khong hop le.")
        if result["status"] == "PASSWORD_TOO_LONG":
            raise HTTPException(
                status_code=400,
                detail="Mat khau qua dai (toi da 72 byte).",
            )
        if result["status"] == "DB_UNAVAILABLE":
            raise HTTPException(status_code=503, detail="SQL Server chua san sang")
        if result["status"] == "USER_EXISTS":
            raise HTTPException(status_code=409, detail="Username hoac email da ton tai.")
        return {
            "accessToken": result["access_token"],
            "expiresAt": result["expires_at"],
            "user": result["user"],
        }

    @router.post("/api/auth/login", response_model=AuthResponse)
    @_limit(_settings_for_limiter.rate_limit_login)
    def login(
        request: Request,
        payload: AuthLoginRequest,
        auth_service: AuthService = Depends(_get_auth_service),
    ):
        result = auth_service.login(payload.identifier, payload.password)
        if result["status"] == "INVALID_INPUT":
            raise HTTPException(status_code=400, detail="Thong tin dang nhap khong hop le.")
        if result["status"] == "DB_UNAVAILABLE":
            raise HTTPException(status_code=503, detail="SQL Server chua san sang")
        if result["status"] == "INVALID_CREDENTIALS":
            raise HTTPException(status_code=401, detail="Sai thong tin dang nhap.")
        return {
            "accessToken": result["access_token"],
            "expiresAt": result["expires_at"],
            "user": result["user"],
        }

    @router.post("/api/auth/logout")
    def logout(
        _payload: AuthLogoutRequest,
        request: Request,
        settings: Settings = Depends(get_app_settings),
    ):
        # Attempt server-side token revocation. Uses the same extraction helper
        # as the auth dependency so the hashed token matches the stored session.
        token = extract_bearer_token(request.headers.get("authorization"))
        revoked = False
        if token:
            revoked = bool(AuthService(settings).logout(token).get("revoked"))
        # Stays 200/idempotent (a second logout is not an error) but the caller
        # can now tell whether a session row was actually revoked.
        return {"status": "SIGNED_OUT", "revoked": revoked}

    @router.get("/api/auth/me", response_model=UserResponse)
    def me(current_user=Depends(get_current_user)):
        return current_user

    @router.post("/api/normalize", response_model=NormalizeResponse)
    @_limit(_settings_for_limiter.rate_limit_normalize)
    def normalize_text(
        request: Request,
        payload: NormalizeRequest,
        current_user=Depends(get_ai_user),
    ):
        pipeline = build_pipeline()
        result = pipeline.normalize(payload.text, submitted_by=current_user["username"])
        return NormalizeResponse(**result.__dict__)

    @router.post("/api/normalize/live", response_model=LiveNormalizeResponse)
    @_limit(_settings_for_limiter.rate_limit_live)
    async def normalize_text_live(
        request: Request,
        payload: LiveNormalizeRequest,
        settings: Settings = Depends(get_app_settings),
        service: PendingAbbreviationService = Depends(_get_pending_service),
        current_user=Depends(get_ai_user),
    ):
        word_map, bigram_freq, context_phrases = await run_in_threadpool(
            _load_diacritic_assets, settings.data_dir
        )
        diacritic_restorer = (
            SyncDiacriticRestorer(
                word_map=word_map,
                detection_threshold=settings.diacritic_detection_threshold,
                min_text_length=settings.diacritic_min_text_length,
                bigram_freq=bigram_freq,
                context_phrases=context_phrases,
            )
            if settings.diacritic_auto_detect and word_map
            else None
        )

        # AI is opt-in per request. The dataset/rule-based path remains fully
        # usable when consent is absent or the user explicitly chooses it off.
        semantic_verifier = get_semantic_verifier(settings) if payload.allow_ai else None
        from app.data_manager.ai_meaning_repo import AIMeaningRepository
        from app.normalizer.ai_meanings import RequestMeanings
        from uuid import uuid4
        request_meanings = RequestMeanings(
            AIMeaningRepository(settings),
            request_id=request.headers.get("Idempotency-Key", str(uuid4()))[:200],
            user_id=str(current_user["id"]),
            session_id=extract_bearer_token(request.headers.get("Authorization")) or "",
            domain=payload.domain, retry=request.headers.get("X-Request-Retry", "0") != "0",
        ) if payload.allow_ai else None

        live_service = LiveNormalizerService(
            settings,
            service,
            diacritic_restorer=diacritic_restorer,
            semantic_verifier=semantic_verifier,
            usage_stats_repository=UsageStatsRepository(settings),
            request_meanings=request_meanings,
        )
        # normalize_live is CPU-bound and synchronous (regex, trie scans, DB
        # round-trips). Running it inline in an async endpoint blocked the event
        # loop for the whole request, so one large paste froze every other user.
        result = await run_in_threadpool(
            live_service.normalize_live,
            payload.text,
            submitted_by=current_user["username"],
            user_id=current_user.get("id"),
            domain=payload.domain,
            resolution_overrides=payload.resolution_overrides,
            input_method=payload.input_method,
        )

        semantic_signal = _has_semantic_verification_signal(result, settings)
        should_verify = _should_apply_semantic_verification(
            input_method=payload.input_method,
            text=payload.text,
            result=result,
            settings=settings,
        )

        # Apply async semantic verification if available. Keep an explicit
        # status when the signal was deferred or the provider is unavailable;
        # a false boolean alone used to look like a successful verification.
        if payload.allow_ai and should_verify:
            if payload.progressive:
                from app.api.live_stream import stream_verification

                return stream_verification(live_service, result, payload.text, word_map, current_user["id"])
            result = await live_service.apply_semantic_verification(
                result,
                original_text=payload.text,
                word_map=word_map,
            )
        elif not semantic_signal:
            result.semantic_status = "not_needed"
            result.semantic_status_reason = "no_semantic_signal"
        elif semantic_verifier is None and payload.allow_ai:
            result.semantic_status = "unavailable"
            result.semantic_status_reason = "provider_unavailable"
        elif semantic_verifier is None:
            result.semantic_status = "not_checked"
            result.semantic_status_reason = "dataset_only"
        else:
            result.semantic_status = "not_checked"
            result.semantic_status_reason = "deferred_until_context"

        return result.to_payload()

    @router.post("/api/normalize/restore-diacritic", response_model=DiacriticRestoreResponse)
    @_limit(_settings_for_limiter.rate_limit_ai)
    async def restore_diacritic(
        request: Request,
        payload: DiacriticRestoreRequest,
        settings: Settings = Depends(get_app_settings),
        current_user=Depends(get_ai_user),
    ):

        ai_client = build_default_client(settings) if payload.allow_ai else NullClient()
        word_map, bigram_freq, context_phrases = await run_in_threadpool(
            _load_diacritic_assets, settings.data_dir
        )
        restorer = DiacriticRestorer(
            settings=settings,
            ai_client=ai_client,
            word_map=word_map,
            bigram_freq=bigram_freq,
            context_phrases=context_phrases,
        )
        result = await restorer.restore(payload.text, force=payload.force)
        return {
            "restoredText": result.restored_text,
            "confidence": result.confidence,
            "changedTokens": [list(pair) for pair in result.changed_tokens],
            "engine": result.engine,
            "fallbackUsed": result.fallback_used,
            "latencyMs": result.latency_ms,
        }

    @router.post("/api/normalize/disambiguate", response_model=DisambiguateResponse)
    @_limit(_settings_for_limiter.rate_limit_ai)
    async def disambiguate_context(
        request: Request,
        payload: DisambiguateRequest,
        settings: Settings = Depends(get_app_settings),
        service: PendingAbbreviationService = Depends(_get_pending_service),
        current_user=Depends(get_ai_user),
    ):
        if not payload.allow_ai:
            raise HTTPException(status_code=409, detail="AI consent is required for disambiguation.")
        disambiguator = get_disambiguator(settings)
        if disambiguator is None or not disambiguator.is_available():
            raise HTTPException(status_code=503, detail="AI provider chua duoc cau hinh.")
        ambiguity_inputs = [
            AmbiguityInput(abbr=a.abbr, options=a.options) for a in payload.ambiguities
        ]
        try:
            result = await disambiguator.disambiguate(
                full_text=payload.text,
                ambiguities=ambiguity_inputs,
            )
        except AIError:
            # Timeout / 429 / provider error must keep the rule-based text rather
            # than surface a 500, matching the documented AI fallback behaviour.
            logging.getLogger(__name__).warning(
                "Disambiguation failed; returning the input unchanged", exc_info=True
            )
            return {
                "refinedText": payload.text,
                "disambiguations": [],
                "confidence": 0.0,
                "fromCache": False,
            }

        # When the AI proposes a meaning outside the dictionary, capture it as
        # a pending suggestion so admins can review and approve it later.
        if not result.from_cache:
            from app.data_manager.ai_meaning_repo import AIMeaningRepository
            from uuid import uuid4
            evidence_repo = AIMeaningRepository(settings)
            evidence_request_id = request.headers.get("Idempotency-Key", str(uuid4()))[:200]
            for d in result.disambiguations:
                if not d.is_new or not d.chosen:
                    continue
                try:
                    evidence_repo.record(
                        abbr=d.abbr,
                        meaning=d.chosen,
                        domain=getattr(payload, "domain", "general"), context=payload.text,
                        request_id=evidence_request_id, user_id=str(current_user["id"]),
                        session_id=extract_bearer_token(request.headers.get("Authorization")) or "",
                        confidence=d.confidence, provider=settings.ai_provider,
                        model=settings.nvidia_model,
                        retry=request.headers.get("X-Request-Retry", "0") != "0",
                    )
                except Exception:  # pragma: no cover - non-fatal best-effort capture
                    logging.getLogger(__name__).warning(
                        "AI meaning evidence write failed in disambiguation",
                    )

        return {
            "refinedText": result.refined_text,
            "disambiguations": [
                {
                    "abbr": d.abbr,
                    "chosen": d.chosen,
                    "confidence": d.confidence,
                    "reason": d.reason,
                    "is_new": d.is_new,
                }
                for d in result.disambiguations
            ],
            "confidence": result.confidence,
            "fromCache": result.from_cache,
        }

    @router.get("/api/abbreviations", response_model=list[AbbreviationResponse])
    def list_abbreviations(
        abbr: str | None = None,
        domain: str | None = None,
        service: PendingAbbreviationService = Depends(_get_pending_service),
        current_user=Depends(get_current_user),
    ):
        return service.list_approved_abbreviations(abbr=abbr, domain=domain)

    @router.post("/api/abbreviations/user-meanings")
    def add_user_abbreviation_meaning(
        payload: UserAbbreviationMeaningRequest,
        service: PendingAbbreviationService = Depends(_get_pending_service),
        current_user=Depends(require_role("admin")),
    ):
        _require_ready(service)
        return service.add_abbreviation_meaning(
            abbr=payload.abbr,
            meaning=payload.meaning,
            reviewer=current_user["username"],
            domain=payload.domain,
            source="api_admin_user_meaning",
            review_notes="Admin added meaning from workspace or dictionary.",
            approve_immediately=True,
        )

    @router.post("/api/abbreviations/add-meaning")
    def add_abbreviation_meaning(
        payload: AddAbbreviationMeaningRequest,
        service: PendingAbbreviationService = Depends(_get_pending_service),
        current_user=Depends(require_role("admin")),
    ):
        _require_ready(service)
        return service.add_abbreviation_meaning(
            abbr=payload.abbr,
            meaning=payload.meaning,
            reviewer=current_user["username"],
            domain=payload.domain,
            source="api_manual_command",
            review_notes=payload.review_notes,
            approve_immediately=payload.approve_immediately,
        )

    @router.get("/api/dictionary/revision")
    def dictionary_revision(
        settings: Settings = Depends(get_app_settings),
        current_user=Depends(get_current_user),
    ):
        from app.data_manager.dictionary_state import DictionaryState
        return {"revision": DictionaryState(settings.data_dir).read()["revision"]}

    @router.get("/api/admin/dictionary/sync-status", response_model=DictionarySyncResponse)
    def dictionary_sync_status(
        settings: Settings = Depends(get_app_settings),
        current_user=Depends(require_role("admin")),
    ):
        from app.data_manager.dictionary_state import DictionaryState
        return DictionaryState(settings.data_dir).read()

    @router.post("/api/admin/dictionary/retry-export", response_model=DictionarySyncResponse)
    def retry_dictionary_export(
        service: PendingAbbreviationService = Depends(_get_pending_service),
        current_user=Depends(require_role("admin")),
    ):
        _require_ready(service)
        return service.sync_approved_abbreviations_to_json()

    @router.get("/api/abbreviations/{abbr}", response_model=AbbreviationResponse)
    def get_abbreviation(
        abbr: str,
        domain: str = "general",
        service: PendingAbbreviationService = Depends(_get_pending_service),
        current_user=Depends(get_current_user),
    ):
        record = service.get_approved_abbreviation_details(abbr, domain=domain)
        if not record:
            raise HTTPException(status_code=404, detail="Khong tim thay tu viet tat.")
        return record

    @router.put("/api/abbreviations/{abbr}", response_model=AbbreviationResponse)
    def save_abbreviation(
        abbr: str,
        payload: AbbreviationUpsertRequest,
        service: PendingAbbreviationService = Depends(_get_pending_service),
        current_user=Depends(require_role("admin")),
    ):
        _require_ready(service)
        try:
            return service.save_approved_abbreviation(
                abbr=abbr,
                expanded=payload.expanded,
                reviewer=current_user["username"],
                alternative_expansions=payload.alternative_expansions,
                domain=payload.domain,
            )
        except ValueError as exc:
            if str(exc) == "INVALID_ABBREVIATION_PAYLOAD":
                raise HTTPException(
                    status_code=400, detail="Tu viet tat va nghia goc khong duoc de trong."
                ) from exc
            raise

    @router.delete("/api/abbreviations/{abbr}")
    def delete_abbreviation(abbr: str, domain: str = "general", service: PendingAbbreviationService = Depends(_get_pending_service), current_user=Depends(require_role("admin"))):
        _require_ready(service)
        try:
            return service.delete_approved_abbreviation(abbr, domain, current_user["username"])
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Khong tim thay tu viet tat.") from exc

    @router.get("/api/pending", response_model=list[PendingAbbreviationResponse])
    def list_pending(
        service: PendingAbbreviationService = Depends(_get_pending_service),
        current_user=Depends(require_role("admin")),
    ):
        _require_ready(service)
        return service.list_pending_abbreviations()

    @router.get("/api/pending/{pending_id}", response_model=PendingAbbreviationResponse)
    def get_pending(
        pending_id: str,
        service: PendingAbbreviationService = Depends(_get_pending_service),
        current_user=Depends(require_role("admin")),
    ):
        _require_ready(service)
        record = service.get_pending_abbreviation_detail(pending_id)
        if not record:
            raise HTTPException(status_code=404, detail="Khong tim thay pending.")
        return record

    @router.post("/api/abbreviations/{pending_id}/approve")
    def approve_abbreviation(
        pending_id: str,
        payload: PendingApprovalRequest,
        service: PendingAbbreviationService = Depends(_get_pending_service),
        current_user=Depends(require_role("admin")),
    ):
        _require_ready(service)
        return service.approve_pending_abbreviation(
            pending_id=pending_id,
            reviewer=current_user["username"],
            expanded=payload.expanded,
            review_notes=payload.review_notes,
        )

    @router.post("/api/abbreviations/{pending_id}/reject")
    def reject_abbreviation(
        pending_id: str,
        payload: PendingRejectionRequest,
        service: PendingAbbreviationService = Depends(_get_pending_service),
        current_user=Depends(require_role("admin")),
    ):
        _require_ready(service)
        return service.reject_pending_abbreviation(
            pending_id=pending_id,
            reviewer=current_user["username"],
            review_notes=payload.review_notes,
        )

    @router.get("/api/history", response_model=list[HistoryEntryResponse])
    def list_current_user_history(
        limit: int = Query(default=30, ge=1, le=100),
        repository: HistoryRepository = Depends(_get_history_repository),
        current_user=Depends(get_current_user),
    ):
        if not repository.is_ready():
            raise HTTPException(status_code=503, detail="SQL Server chua san sang")
        return repository.list_history(user_id=current_user["id"], limit=limit)

    @router.post("/api/history", response_model=HistoryEntryResponse)
    @_limit(_settings_for_limiter.rate_limit_history)
    def create_history_entry(
        request: Request,
        payload: HistoryCreateRequest,
        repository: HistoryRepository = Depends(_get_history_repository),
        current_user=Depends(get_current_user),
    ):
        if not repository.is_ready():
            raise HTTPException(status_code=503, detail="SQL Server chua san sang")
        if not payload.input_text.strip():
            raise HTTPException(status_code=400, detail="Khong the luu lich su voi noi dung rong.")
        try:
            return repository.log_normalization(
                input_text=payload.input_text,
                output_text=payload.output_text if payload.output_text else None,
                error_types=payload.error_types,
                latency_ms=payload.latency_ms,
                domain=payload.domain,
                source_kind=payload.source_kind,
                username_snapshot=current_user["username"],
                user_id=current_user["id"],
            )
        except Exception as exc:
            try:
                from sqlalchemy.exc import SQLAlchemyError as _SAError
            except ImportError:  # pragma: no cover - optional dependency in early setup
                raise
            if isinstance(exc, _SAError):
                # History is user-requested persistence: answer 503 so the UI can
                # retry, instead of letting a DB blip surface as a generic 500.
                logging.getLogger(__name__).warning(
                    "History write failed; SQL Server unavailable.", exc_info=True
                )
                raise HTTPException(
                    status_code=503, detail="SQL Server chua san sang"
                ) from exc
            raise

    @router.delete("/api/history/{history_id}", response_model=HistoryEntryResponse)
    def delete_current_user_history_entry(
        history_id: str,
        repository: HistoryRepository = Depends(_get_history_repository),
        current_user=Depends(get_current_user),
    ):
        if not repository.is_ready():
            raise HTTPException(status_code=503, detail="SQL Server chua san sang")
        try:
            return repository.delete_history_entry(history_id, user_id=current_user["id"])
        except ValueError as exc:
            if str(exc) == "HISTORY_NOT_FOUND":
                raise HTTPException(
                    status_code=404, detail="Khong tim thay ban ghi lich su."
                ) from exc
            raise

    @router.get("/api/users", response_model=list[UserResponse])
    def list_users(
        repository: UserRepository = Depends(_get_user_repository),
        current_user=Depends(require_role("admin")),
    ):
        if not repository.is_ready():
            raise HTTPException(status_code=503, detail="SQL Server chua san sang")
        return repository.list_users()

    @router.delete("/api/users/{user_id}", response_model=UserResponse)
    def delete_user(
        user_id: str,
        repository: UserRepository = Depends(_get_user_repository),
        current_user=Depends(require_role("admin")),
    ):
        if not repository.is_ready():
            raise HTTPException(status_code=503, detail="SQL Server chua san sang")
        try:
            return repository.delete_user(user_id)
        except ValueError as exc:
            if str(exc) == "USER_NOT_FOUND":
                raise HTTPException(status_code=404, detail="Khong tim thay tai khoan.") from exc
            if str(exc) == "ADMIN_USER_DELETE_FORBIDDEN":
                raise HTTPException(
                    status_code=400, detail="Tai khoan admin khong the bi xoa."
                ) from exc
            raise

    @router.post("/api/users/{user_id}/roles", response_model=UserResponse)
    def assign_role(
        user_id: str,
        payload: AssignRoleRequest,
        current_user=Depends(require_role("admin")),
    ):
        raise HTTPException(
            status_code=405, detail="Vai tro user/admin da co dinh va khong the thay doi."
        )

    @router.get("/api/admin/ai-usage")
    def ai_usage_stats(
        current_user=Depends(require_role("admin")),
    ):
        from app.ai.client import get_ai_usage_stats
        return get_ai_usage_stats()

    # --- User Sessions ---

    @router.get("/api/sessions")
    def list_my_sessions(
        current_user=Depends(get_current_user),
        settings: Settings = Depends(get_app_settings),
    ):
        from app.data_manager.new_tables_repo import SessionRepository
        repo = SessionRepository(settings)
        if not repo.is_ready():
            return []
        return repo.get_active_sessions(current_user["id"])

    @router.post("/api/sessions/revoke-all")
    def revoke_all_sessions(
        current_user=Depends(get_current_user),
        settings: Settings = Depends(get_app_settings),
    ):
        from app.data_manager.new_tables_repo import SessionRepository
        repo = SessionRepository(settings)
        if not repo.is_ready():
            raise HTTPException(status_code=503, detail="SQL Server chua san sang")
        try:
            count = repo.revoke_all_user_sessions(current_user["id"])
        except Exception as exc:
            try:
                from sqlalchemy.exc import SQLAlchemyError as _SAError
            except ImportError:  # pragma: no cover - optional dependency in early setup
                raise
            if isinstance(exc, _SAError):
                # Revoking sessions is a security action: a DB failure must not
                # answer 200 {"revoked": 0} while old sessions stay valid.
                logging.getLogger(__name__).warning(
                    "Revoke-all failed; SQL Server unavailable.", exc_info=True
                )
                raise HTTPException(
                    status_code=503, detail="SQL Server chua san sang"
                ) from exc
            raise
        return {"revoked": count}

    # --- User Preferences ---

    @router.get("/api/preferences")
    def get_preferences(
        category: Optional[str] = None,
        current_user=Depends(get_current_user),
        settings: Settings = Depends(get_app_settings),
    ):
        from app.data_manager.new_tables_repo import PreferencesRepository
        repo = PreferencesRepository(settings)
        if not repo.is_ready():
            return []
        return repo.get_all(current_user["id"], category)

    @router.put("/api/preferences/{key}")
    def set_preference(
        key: str,
        payload: PreferenceSetRequest,
        current_user=Depends(get_current_user),
        settings: Settings = Depends(get_app_settings),
    ):
        from app.data_manager.new_tables_repo import PreferencesRepository
        repo = PreferencesRepository(settings)
        if not repo.is_ready():
            raise HTTPException(status_code=503, detail="Preferences not available")
        ok = repo.set(current_user["id"], key, payload.value, payload.category)
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to save preference")
        return {"key": key, "value": payload.value, "category": payload.category}

    @router.delete("/api/preferences/{key}")
    def delete_preference(
        key: str,
        current_user=Depends(get_current_user),
        settings: Settings = Depends(get_app_settings),
    ):
        from app.data_manager.new_tables_repo import PreferencesRepository
        repo = PreferencesRepository(settings)
        if not repo.is_ready():
            raise HTTPException(status_code=503, detail="Preferences not available")
        deleted = repo.delete(current_user["id"], key)
        if not deleted:
            raise HTTPException(status_code=404, detail="Preference not found")
        return {"deleted": key}

    # --- Phrase Overrides (admin) ---

    @router.get("/api/admin/phrase-overrides")
    def list_phrase_overrides(
        domain: Optional[str] = None,
        current_user=Depends(require_role("admin")),
        settings: Settings = Depends(get_app_settings),
    ):
        from app.data_manager.new_tables_repo import PhraseOverrideRepository
        repo = PhraseOverrideRepository(settings)
        if not repo.is_ready():
            return []
        return repo.get_active(domain)

    @router.post("/api/admin/phrase-overrides")
    def create_phrase_override(
        payload: PhraseOverrideCreateRequest,
        current_user=Depends(require_role("admin")),
        settings: Settings = Depends(get_app_settings),
    ):
        from app.data_manager.new_tables_repo import PhraseOverrideRepository
        repo = PhraseOverrideRepository(settings)
        if not repo.is_ready():
            raise HTTPException(status_code=503, detail="Phrase overrides not available")
        result = repo.create(
            phrase_key=payload.phrase_key,
            phrase_value=payload.phrase_value,
            domain=payload.domain,
            source="admin",
            priority=payload.priority,
            notes=payload.notes,
            created_by=current_user.get("username"),
        )
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create phrase override")
        # Without this the admin waits out the 15s live-data TTL and concludes
        # the override "did not work".
        PendingAbbreviationService.invalidate_live_normalization_cache()
        from app.data_manager.dictionary_state import DictionaryState
        DictionaryState(settings.data_dir).bump()
        return result

    @router.put("/api/admin/phrase-overrides/{override_id}")
    def update_phrase_override(
        override_id: str,
        payload: PhraseOverrideUpdateRequest,
        current_user=Depends(require_role("admin")),
        settings: Settings = Depends(get_app_settings),
    ):
        from app.data_manager.new_tables_repo import PhraseOverrideRepository
        repo = PhraseOverrideRepository(settings)
        if not repo.is_ready():
            raise HTTPException(status_code=503, detail="Phrase overrides not available")
        ok = repo.update(
            override_id=override_id,
            phrase_value=payload.phrase_value,
            priority=payload.priority,
            notes=payload.notes,
            updated_by=current_user.get("username"),
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Override not found")
        PendingAbbreviationService.invalidate_live_normalization_cache()
        from app.data_manager.dictionary_state import DictionaryState
        DictionaryState(settings.data_dir).bump()
        return {"updated": override_id}

    @router.delete("/api/admin/phrase-overrides/{override_id}")
    def delete_phrase_override(
        override_id: str,
        current_user=Depends(require_role("admin")),
        settings: Settings = Depends(get_app_settings),
    ):
        from app.data_manager.new_tables_repo import PhraseOverrideRepository
        repo = PhraseOverrideRepository(settings)
        if not repo.is_ready():
            raise HTTPException(status_code=503, detail="Phrase overrides not available")
        ok = repo.soft_delete(override_id, updated_by=current_user.get("username"))
        if not ok:
            raise HTTPException(status_code=404, detail="Override not found")
        PendingAbbreviationService.invalidate_live_normalization_cache()
        from app.data_manager.dictionary_state import DictionaryState
        DictionaryState(settings.data_dir).bump()
        return {"deleted": override_id}

    # --- Usage Stats (admin) ---

    @router.get("/api/admin/usage-stats/top")
    def top_abbreviations(
        days: int = Query(default=30, ge=1, le=365),
        limit: int = Query(default=50, ge=1, le=200),
        current_user=Depends(require_role("admin")),
        settings: Settings = Depends(get_app_settings),
    ):
        from app.data_manager.new_tables_repo import UsageStatsRepository
        repo = UsageStatsRepository(settings)
        if not repo.is_ready():
            return []
        return repo.get_top_abbreviations(days=days, limit=limit)

    @router.get("/api/admin/usage-stats/daily")
    def daily_usage_stats(
        days: int = Query(default=7, ge=1, le=90),
        current_user=Depends(require_role("admin")),
        settings: Settings = Depends(get_app_settings),
    ):
        from app.data_manager.new_tables_repo import UsageStatsRepository
        repo = UsageStatsRepository(settings)
        if not repo.is_ready():
            return []
        return repo.get_daily_stats(days=days)

    @router.get("/api/health")
    @_limit(_settings_for_limiter.rate_limit_health)
    def health(request: Request, settings: Settings = Depends(get_app_settings)):
        ok = _cached_health(settings or get_settings())
        # Do NOT leak the raw exception text — it can include driver/server details.
        return {
            "status": "ok" if ok else "degraded",
            "detail": "OK" if ok else "Database not reachable.",
        }
