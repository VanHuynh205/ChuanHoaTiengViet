from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Callable, List, TypeVar

# ``app/`` lives inside ``backend/``; the repository root is one level above it.
BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
# Backwards-compatible alias: everything the backend resolves relatively is
# rooted at ``backend/``.
ROOT_DIR = BACKEND_DIR
DEFAULT_DATA_DIR = BACKEND_DIR / "data"
LEGACY_DATA_DIR = BACKEND_DIR / "DataTuVietTat_and_TuDienTiengViet"

# Development-only sentinel. ``Settings.validate()`` rejects it in every
# environment unless ALLOW_DEV_AUTH_SECRET is set explicitly, so forgetting to
# set APP_ENV can no longer leave the process signing tokens with a constant
# that is published in this repository.
AUTH_SECRET_DEV_FALLBACK = "__DEV_AUTH_SECRET_UNSAFE_DO_NOT_USE_IN_PRODUCTION__"  # nosec B105
AUTH_SECRET_MIN_LENGTH = 32

# Per-process random secret used when AUTH_SECRET is unset. Generated once at
# import time so every ``Settings()`` in the process shares it (tokens minted by
# one request stay verifiable by the next), but never survives a restart.
_RUNTIME_DEV_AUTH_SECRET = secrets.token_urlsafe(48)

T = TypeVar("T")


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        return

    # ``.env`` may sit next to the backend or at the repository root (the
    # historical location, shared with the frontend tooling).
    for env_file in (BACKEND_DIR / ".env", PROJECT_ROOT / ".env"):
        if env_file.exists():
            load_dotenv(env_file)
            return


_load_dotenv()


def _raw_env(name: str, default: str) -> str:
    """Return the env var, treating an empty/whitespace value as 'unset'."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw


def _parse_env(name: str, default: str, caster: Callable[[str], T], expected: str) -> T:
    """Cast an env var, raising a message that names the offending variable.

    A typo in a numeric env var used to surface as a bare ``ValueError`` raised
    while importing ``app.config`` — killing every entrypoint with a traceback
    that never said which variable was wrong. Values are still never silently
    coerced back to the default: a wrong value is a configuration bug.
    """
    raw = _raw_env(name, default)
    try:
        return caster(raw.strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Bien moi truong {name}={raw!r} khong hop le: can {expected}.") from exc


def _env_flag(name: str, default: str = "0") -> bool:
    return _raw_env(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: str) -> float:
    return _parse_env(name, default, float, "so thuc")


def _env_int(name: str, default: str) -> int:
    return _parse_env(name, default, int, "so nguyen")


def _env_str(name: str, default: str) -> str:
    return _raw_env(name, default)


def _lazy(factory: Callable[[], T]) -> T:
    """Declare a dataclass default that is evaluated at instantiation time.

    ``Settings`` used to read ``os.getenv`` in the class body, which froze every
    value at import time: ``reset_settings_cache()`` then re-created a
    ``Settings`` with the exact same stale defaults. ``default_factory`` keeps
    ``Settings(auth_secret=...)`` working while making ``Settings()`` actually
    re-read the environment.
    """
    return field(default_factory=factory)


@dataclass(frozen=True)
class Settings:
    sql_driver: str = _lazy(lambda: _env_str("SQL_DRIVER", "ODBC Driver 18 for SQL Server"))
    sql_mode: str = _lazy(lambda: _env_str("SQL_MODE", "sqlexpress").strip().lower())
    sql_host: str = _lazy(lambda: _env_str("SQL_HOST", "localhost"))
    sql_instance: str = _lazy(lambda: _env_str("SQL_INSTANCE", "SQLEXPRESS"))
    sql_database: str = _lazy(lambda: _env_str("SQL_DATABASE", "VietNormalizer"))
    sql_auth: str = _lazy(lambda: _env_str("SQL_AUTH", "sql").strip().lower())
    sql_username: str = _lazy(lambda: _env_str("SQL_USERNAME", "normalizer_app"))
    sql_password: str = _lazy(lambda: os.getenv("SQL_PASSWORD", ""))
    sql_encrypt: str = _lazy(lambda: _env_str("SQL_ENCRYPT", "yes"))
    sql_trust_server_certificate: str = _lazy(
        lambda: _env_str("SQL_TRUST_SERVER_CERTIFICATE", "yes")
    )
    sql_echo: bool = _lazy(lambda: _env_flag("SQL_ECHO", "0"))
    cli_assume_admin: bool = _lazy(lambda: _env_flag("CLI_ASSUME_ADMIN", "0"))
    auth_secret: str = _lazy(lambda: os.getenv("AUTH_SECRET") or _RUNTIME_DEV_AUTH_SECRET)
    auth_token_ttl_minutes: int = _lazy(lambda: _env_int("AUTH_TOKEN_TTL_MINUTES", "120"))
    # Explicit escape hatch for the published dev sentinel. Without it, an
    # AUTH_SECRET equal to AUTH_SECRET_DEV_FALLBACK is a fatal config error in
    # every environment, not just production.
    allow_dev_auth_secret: bool = _lazy(lambda: _env_flag("ALLOW_DEV_AUTH_SECRET", "0"))
    web_origin: str = _lazy(lambda: _env_str("WEB_ORIGIN", "http://localhost:5173"))
    app_env: str = _lazy(lambda: _env_str("APP_ENV", "development").strip().lower())
    data_dir: Path = _lazy(lambda: Path(_env_str("DATA_DIR", str(DEFAULT_DATA_DIR))))

    # Account lockout after repeated failed logins (columns already exist in
    # dbo.users). 0 disables the feature.
    auth_max_failed_logins: int = _lazy(lambda: _env_int("AUTH_MAX_FAILED_LOGINS", "10"))
    auth_lockout_minutes: int = _lazy(lambda: _env_int("AUTH_LOCKOUT_MINUTES", "15"))

    # Hard cap on the raw request body, enforced before FastAPI buffers it.
    max_request_body_bytes: int = _lazy(lambda: _env_int("MAX_REQUEST_BODY_BYTES", "1048576"))

    # Rate limiting (per-user when authenticated, else per-IP via slowapi).
    rate_limit_enabled: bool = _lazy(lambda: _env_flag("RATE_LIMIT_ENABLED", "1"))
    rate_limit_login: str = _lazy(lambda: _env_str("RATE_LIMIT_LOGIN", "10/minute"))
    rate_limit_register: str = _lazy(lambda: _env_str("RATE_LIMIT_REGISTER", "5/minute"))
    rate_limit_ai: str = _lazy(lambda: _env_str("RATE_LIMIT_AI", "60/minute"))
    # Batch /api/normalize is one-shot per submission.
    rate_limit_normalize: str = _lazy(lambda: _env_str("RATE_LIMIT_NORMALIZE", "120/minute"))
    # /api/normalize/live fires on every keystroke (debounced ~120ms). At ~8 req/s
    # a fast typist easily reaches 400+/min, so the cap must be much higher.
    rate_limit_live: str = _lazy(lambda: _env_str("RATE_LIMIT_LIVE", "600/minute"))
    rate_limit_history: str = _lazy(lambda: _env_str("RATE_LIMIT_HISTORY", "60/minute"))
    rate_limit_health: str = _lazy(lambda: _env_str("RATE_LIMIT_HEALTH", "60/minute"))
    # Long pasted paragraphs can contain many unknown tokens. Cap best-effort
    # moderation submissions so normalization output stays fast and complete.
    live_max_pending_submissions: int = _lazy(
        lambda: _env_int("LIVE_MAX_PENDING_SUBMISSIONS", "80")
    )
    # Avoid returning many full-size variant copies for long texts with many
    # ambiguities. The primary output remains complete; ambiguity metadata stays.
    live_variant_max_ambiguities: int = _lazy(lambda: _env_int("LIVE_VARIANT_MAX_AMBIGUITIES", "12"))
    live_incremental_min_chars: int = _lazy(lambda: _env_int("LIVE_INCREMENTAL_MIN_CHARS", "1200"))
    live_incremental_chunk_words: int = _lazy(lambda: _env_int("LIVE_INCREMENTAL_CHUNK_WORDS", "120"))
    live_incremental_cache_size: int = _lazy(lambda: _env_int("LIVE_INCREMENTAL_CACHE_SIZE", "512"))
    # Bound on the process-wide live-normalization-data cache. Each entry holds
    # per-domain/per-user abbreviation maps, so this must never be unbounded.
    live_data_cache_max_entries: int = _lazy(lambda: _env_int("LIVE_DATA_CACHE_MAX_ENTRIES", "64"))

    # AI provider
    ai_provider: str = _lazy(lambda: _env_str("AI_PROVIDER", "nvidia").strip().lower())
    nvidia_api_key: str = _lazy(lambda: os.getenv("NVIDIA_API_KEY", ""))
    nvidia_model: str = _lazy(lambda: _env_str("NVIDIA_MODEL", "google/gemma-4-31b-it"))
    nvidia_base_url: str = _lazy(
        lambda: _env_str("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    )
    nvidia_reasoning_effort: str = _lazy(lambda: _env_str("NVIDIA_REASONING_EFFORT", "low"))
    nvidia_reasoning_token_reserve: int = _lazy(lambda: _env_int("NVIDIA_REASONING_TOKEN_RESERVE", "2048"))
    nvidia_reasoning_budget: int = _lazy(lambda: _env_int("NVIDIA_REASONING_BUDGET", "256"))
    nvidia_enable_thinking: bool = _lazy(lambda: _env_flag("NVIDIA_ENABLE_THINKING", "1"))
    nvidia_clear_thinking: bool = _lazy(lambda: _env_flag("NVIDIA_CLEAR_THINKING", "0"))
    ai_timeout_seconds: int = _lazy(lambda: _env_int("AI_TIMEOUT_SECONDS", "90"))
    ai_max_retries: int = _lazy(lambda: _env_int("AI_MAX_RETRIES", "2"))
    ai_fallback_to_rules: bool = _lazy(lambda: _env_flag("AI_FALLBACK_TO_RULES", "1"))
    ai_disable_network: bool = _lazy(lambda: _env_flag("AI_DISABLE_NETWORK", "0"))
    ai_rate_limit_cooldown_seconds: float = _lazy(
        lambda: _env_float("AI_RATE_LIMIT_COOLDOWN", "60")
    )
    # Upper bound on requested completion tokens, shared by every AI call site.
    ai_max_output_tokens: int = _lazy(lambda: _env_int("AI_MAX_OUTPUT_TOKENS", "8192"))
    # Application limits, not claims about provider quota. Shared by local workers.
    ai_budget_path: str = _lazy(lambda: _env_str("AI_BUDGET_PATH", ".runtime/ai-budget.sqlite3"))
    ai_budget_window_seconds: int = _lazy(lambda: _env_int("AI_BUDGET_WINDOW_SECONDS", "60"))
    ai_requests_per_window: int = _lazy(lambda: _env_int("AI_REQUESTS_PER_WINDOW", "30"))
    ai_user_requests_per_window: int = _lazy(lambda: _env_int("AI_USER_REQUESTS_PER_WINDOW", "10"))
    ai_max_concurrency: int = _lazy(lambda: _env_int("AI_MAX_CONCURRENCY", "4"))
    ai_user_max_concurrency: int = _lazy(lambda: _env_int("AI_USER_MAX_CONCURRENCY", "2"))

    # Diacritic restoration
    diacritic_auto_detect: bool = _lazy(lambda: _env_flag("DIACRITIC_AUTO_DETECT", "1"))
    diacritic_detection_threshold: float = _lazy(
        lambda: _env_float("DIACRITIC_DETECTION_THRESHOLD", "0.6")
    )
    diacritic_min_text_length: int = _lazy(lambda: _env_int("DIACRITIC_MIN_TEXT_LENGTH", "8"))

    # Phrase-level normalization
    phrase_max_ngram: int = _lazy(lambda: _env_int("PHRASE_MAX_NGRAM", "5"))
    phrase_min_freq: int = _lazy(lambda: _env_int("PHRASE_MIN_FREQ", "3"))

    # Semantic verification (AI post-processing)
    semantic_verify_enabled: bool = _lazy(lambda: _env_flag("SEMANTIC_VERIFY_ENABLED", "1"))
    semantic_verify_confidence_threshold: float = _lazy(
        lambda: _env_float("SEMANTIC_VERIFY_CONFIDENCE_THRESHOLD", "0.7")
    )
    semantic_verify_max_tokens: int = _lazy(lambda: _env_int("SEMANTIC_VERIFY_MAX_TOKENS", "200"))
    # Measured on the NVIDIA free tier a 400-word chunk completes in roughly
    # 20-50s with thinking disabled, well inside the shared 90s deadline;
    # 800-word chunks needed 40-70s and regularly timed out.
    semantic_review_chunk_words: int = _lazy(lambda: _env_int("SEMANTIC_REVIEW_CHUNK_WORDS", "400"))
    semantic_fallback_model: str = _lazy(lambda: _env_str("SEMANTIC_FALLBACK_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b"))
    semantic_verify_max_chunks: int = _lazy(lambda: _env_int("SEMANTIC_VERIFY_MAX_CHUNKS", "64"))
    semantic_verify_max_concurrency: int = _lazy(
        lambda: _env_int("SEMANTIC_VERIFY_MAX_CONCURRENCY", "2")
    )
    semantic_verify_paste_min_chars: int = _lazy(
        lambda: _env_int("SEMANTIC_VERIFY_PASTE_MIN_CHARS", "80")
    )
    semantic_verify_typing_min_chars: int = _lazy(
        lambda: _env_int("SEMANTIC_VERIFY_TYPING_MIN_CHARS", "120")
    )
    semantic_verify_min_diacritic_changes: int = _lazy(
        lambda: _env_int("SEMANTIC_VERIFY_MIN_DIACRITIC_CHANGES", "2")
    )

    @property
    def is_production(self) -> bool:
        return self.app_env in {"production", "prod"}

    def validate(self) -> List[str]:
        """Return a list of fatal config errors. Empty list means OK."""
        errors: List[str] = []
        if self.nvidia_reasoning_effort not in {"low", "high", "max"}:
            errors.append("NVIDIA_REASONING_EFFORT must be low, high or max.")
        if self.nvidia_reasoning_token_reserve < 0:
            errors.append("NVIDIA_REASONING_TOKEN_RESERVE must not be negative.")

        for name in ("ai_budget_window_seconds", "ai_requests_per_window",
                     "ai_user_requests_per_window", "ai_max_concurrency",
                     "ai_user_max_concurrency", "ai_timeout_seconds"):
            if getattr(self, name) <= 0:
                errors.append(f"{name.upper()} must be positive.")
        if not 0 <= self.ai_max_retries <= 5:
            errors.append("AI_MAX_RETRIES must be between 0 and 5.")
        if self.ai_user_requests_per_window > self.ai_requests_per_window:
            errors.append("AI_USER_REQUESTS_PER_WINDOW must not exceed AI_REQUESTS_PER_WINDOW.")
        if self.ai_user_max_concurrency > self.ai_max_concurrency:
            errors.append("AI_USER_MAX_CONCURRENCY must not exceed AI_MAX_CONCURRENCY.")

        # --- Checks that apply in EVERY environment -------------------------
        # Forgetting APP_ENV used to disable all of these silently.
        if self.auth_secret == AUTH_SECRET_DEV_FALLBACK and not self.allow_dev_auth_secret:
            errors.append(
                "AUTH_SECRET is the published development sentinel. Set a real AUTH_SECRET, "
                "or set ALLOW_DEV_AUTH_SECRET=1 to acknowledge the risk explicitly."
            )
        if len(self.auth_secret) < AUTH_SECRET_MIN_LENGTH:
            errors.append(
                f"AUTH_SECRET must be at least {AUTH_SECRET_MIN_LENGTH} characters."
            )

        # --- Production-only hardening --------------------------------------
        if self.is_production:
            if self.allow_dev_auth_secret:
                errors.append("ALLOW_DEV_AUTH_SECRET must not be enabled in production.")
            if self.cli_assume_admin:
                errors.append("CLI_ASSUME_ADMIN must be disabled in production.")
            if self.ai_provider == "nvidia" and not self.nvidia_api_key:
                errors.append("NVIDIA_API_KEY must be set when AI_PROVIDER=nvidia in production.")
            origin = self.web_origin.strip()
            if "*" in origin:
                errors.append("WEB_ORIGIN must not contain '*' in production (CORS wildcard).")
            elif origin.startswith("http://") and not origin.startswith("http://localhost"):
                errors.append("WEB_ORIGIN must use https:// in production.")
            elif "localhost" in origin or "127.0.0.1" in origin:
                errors.append("WEB_ORIGIN still points at localhost in production.")
        return errors


@lru_cache(maxsize=1)
def _cached_settings() -> Settings:
    return Settings()


def get_settings() -> Settings:
    """Return the process-wide singleton ``Settings`` instance.

    Cached so downstream caches keyed by ``Settings`` identity hit the same key.
    """
    return _cached_settings()


def reset_settings_cache() -> None:
    """Clear the cached settings — intended for tests that mutate environment vars."""
    _cached_settings.cache_clear()
