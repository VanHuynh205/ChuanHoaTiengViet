from __future__ import annotations

import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from threading import Lock
from typing import AbstractSet, ClassVar, Dict, List, Optional, Set, Tuple

from app.config import Settings
from app.data_manager.abbreviation_repo import AbbreviationRepository
from app.data_manager.db import health_check
from app.data_manager.dictionary_state import DictionaryState, DictionaryWriteCommittedError
from app.data_manager.json_sync import JsonDataStore
from app.data_manager.new_tables_repo import PhraseOverrideRepository


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiveNormalizationData:
    abbreviations: Dict[str, str]
    # Read-only: the same object is shared by every cached entry.
    dictionary_words: AbstractSet[str]
    approved_details: Dict[str, dict]
    phrase_overrides: Dict[str, dict] = field(default_factory=dict)
    db_phrases: Dict[str, dict] = field(default_factory=dict)
    mined_phrases: Dict[str, dict] = field(default_factory=dict)
    revision: int = 0


@dataclass(frozen=True)
class _LiveNormalizationCacheEntry:
    data: LiveNormalizationData
    expires_at: float


@dataclass(frozen=True)
class _SharedBootstrapData:
    """The parts of the live data that depend on NEITHER domain nor user.

    Hoisting these out of the per-(domain, user) cache is what stops every cache
    entry from carrying its own ~7.5 MB copy of the 73k-word dictionary, and
    stops a cache miss from re-parsing ~59 MB of dictionary JSON.
    """

    json_abbreviations: Dict[str, str]
    json_details: Dict[str, dict]
    dictionary_words: AbstractSet[str]
    mined_phrases: Dict[str, dict]


class PendingAbbreviationService:
    _live_data_cache_ttl_seconds: ClassVar[float] = 15.0
    # Bounded LRU: the key includes ``user_id`` and a client-supplied ``domain``,
    # so an unbounded dict grew without limit and never dropped stale entries.
    _live_data_cache: ClassVar[
        "OrderedDict[Tuple[Settings, str, Optional[str], int], _LiveNormalizationCacheEntry]"
    ] = OrderedDict()
    _live_data_cache_lock: ClassVar[Lock] = Lock()
    _live_data_cache_generation: ClassVar[int] = 0

    # Shared, immutable bootstrap payload (per Settings), rebuilt on the same
    # TTL as the live data cache but stored exactly once.
    _shared_bootstrap_ttl_seconds: ClassVar[float] = 60.0
    _shared_bootstrap_cache: ClassVar[Dict[Tuple[Settings, int], Tuple[_SharedBootstrapData, float]]] = {}
    _shared_bootstrap_lock: ClassVar[Lock] = Lock()

    # Short-lived replay of the last moderation submission per (abbr, domain).
    _pending_submit_ttl_seconds: ClassVar[float] = 30.0
    _pending_submit_cache_max: ClassVar[int] = 512
    _pending_submit_cache: ClassVar[
        "OrderedDict[Tuple[Settings, str, str], Tuple[dict, float]]"
    ] = OrderedDict()
    _pending_submit_lock: ClassVar[Lock] = Lock()

    _health_cache_ttl_seconds: ClassVar[float] = 30.0
    _health_cache: ClassVar[Dict[Settings, Tuple[bool, float]]] = {}
    _health_cache_lock: ClassVar[Lock] = Lock()

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.json_store = JsonDataStore(settings)
        self.repository = AbbreviationRepository(settings)
        self.phrase_override_repository = PhraseOverrideRepository(settings)

    def db_is_ready(self) -> bool:
        if not self.repository.is_ready():
            return False
        now = time.monotonic()
        with self._health_cache_lock:
            cached = self._health_cache.get(self.settings)
            if cached and cached[1] > now:
                return cached[0]
        ok, _ = health_check(self.settings)
        with self._health_cache_lock:
            self._health_cache[self.settings] = (ok, now + self._health_cache_ttl_seconds)
        return ok

    def get_approved_abbreviations(self) -> Dict[str, str]:
        json_abbreviations = self.json_store.load_abbreviations()
        if self.db_is_ready():
            approved = self.repository.get_approved_abbreviation_map()
            if approved:
                merged = dict(json_abbreviations)
                merged.update(approved)
                return merged
        return json_abbreviations

    def get_dictionary_words(self) -> Set[str]:
        if self.db_is_ready():
            words = self.repository.get_dictionary_words()
            if words:
                return words
        return self.json_store.load_dictionary_words()

    def get_live_normalization_data(
        self,
        domain: str = "general",
        user_id: Optional[str] = None,
    ) -> LiveNormalizationData:
        revision = self.dictionary_revision()
        cache_key = (self.settings, domain, user_id, revision)
        now = time.monotonic()
        with self._live_data_cache_lock:
            cached = self._live_data_cache.get(cache_key)
            if cached and cached.expires_at > now:
                self._live_data_cache.move_to_end(cache_key)
                return cached.data

        data = replace(self._load_live_normalization_data(domain=domain, user_id=user_id),
                       revision=revision)
        with self._live_data_cache_lock:
            self._prune_live_data_cache_locked(time.monotonic())
            self._live_data_cache[cache_key] = _LiveNormalizationCacheEntry(
                data=data,
                expires_at=time.monotonic() + self._live_data_cache_ttl_seconds,
            )
            self._live_data_cache.move_to_end(cache_key)
            max_entries = max(1, getattr(self.settings, "live_data_cache_max_entries", 64))
            while len(self._live_data_cache) > max_entries:
                self._live_data_cache.popitem(last=False)
        return data

    @classmethod
    def _prune_live_data_cache_locked(cls, now: float) -> None:
        """Drop expired entries. Caller must hold ``_live_data_cache_lock``."""
        expired = [key for key, entry in cls._live_data_cache.items() if entry.expires_at <= now]
        for key in expired:
            cls._live_data_cache.pop(key, None)

    def _get_shared_bootstrap(self) -> _SharedBootstrapData:
        """Return the domain/user-independent slice of the live data.

        Loaded once per ``Settings`` instead of once per (domain, user) cache
        entry: ``load_dictionary_words()`` alone parses tens of megabytes of
        JSON and yields a 73k-entry set.
        """
        now = time.monotonic()
        cache_key = (self.settings, self.dictionary_revision())
        with self._shared_bootstrap_lock:
            cached = self._shared_bootstrap_cache.get(cache_key)
            if cached and cached[1] > now:
                return cached[0]

        if hasattr(self.json_store, "load_abbreviation_details"):
            json_details = self.json_store.load_abbreviation_details()
            json_abbreviations = {
                abbr: record["expanded"]
                for abbr, record in json_details.items()
                if record.get("expanded")
            }
        else:
            json_abbreviations = self.json_store.load_abbreviations()
            json_details = {}

        data = _SharedBootstrapData(
            json_abbreviations=json_abbreviations,
            json_details=json_details,
            dictionary_words=frozenset(self.json_store.load_dictionary_words()),
            mined_phrases=self.json_store.load_mined_phrases(),
        )
        with self._shared_bootstrap_lock:
            for old_key in list(self._shared_bootstrap_cache):
                if old_key[0] == self.settings:
                    self._shared_bootstrap_cache.pop(old_key)
            self._shared_bootstrap_cache[cache_key] = (
                data,
                time.monotonic() + self._shared_bootstrap_ttl_seconds,
            )
        return data

    def dictionary_sync_status(self) -> dict:
        return DictionaryState(self.settings.data_dir).read()

    def dictionary_revision(self) -> int:
        return int(self.dictionary_sync_status()["revision"])

    def _load_live_normalization_data(
        self,
        domain: str = "general",
        user_id: Optional[str] = None,
    ) -> LiveNormalizationData:
        shared = self._get_shared_bootstrap()
        json_abbreviations = shared.json_abbreviations
        json_details = shared.json_details
        db_ready = self.db_is_ready()
        phrase_overrides = self._load_phrase_overrides(domain=domain, db_ready=db_ready)
        mined_phrases = shared.mined_phrases
        if not db_ready:
            return LiveNormalizationData(
                # Shallow copies: the shared bootstrap payload is handed to every
                # request, so callers must never be able to mutate it in place.
                abbreviations=dict(json_abbreviations),
                dictionary_words=shared.dictionary_words,
                approved_details=dict(json_details),
                phrase_overrides=phrase_overrides,
                db_phrases={},
                mined_phrases=mined_phrases,
            )

        approved_records = self.repository.list_approved_abbreviations()
        abbreviations = dict(json_abbreviations)
        abbreviations.update(
            {
                record["abbr"].strip().lower(): record["expanded"].strip()
                for record in approved_records
                if record.get("abbr") and record.get("expanded")
            }
        )

        dictionary_words: AbstractSet[str] = self.repository.get_dictionary_words()
        if not dictionary_words:
            # Reuse the shared frozenset instead of re-parsing the dictionary
            # JSON (~59 MB) for every (domain, user) cache entry.
            dictionary_words = shared.dictionary_words

        approved_details = dict(json_details)
        approved_details.update(
            {
                record["abbr"].strip().lower(): record
                for record in approved_records
                if record.get("abbr") and record.get("domain", "general") == domain
            }
        )
        db_phrases: Dict[str, dict] = {}
        for record in approved_records:
            abbr = str(record.get("abbr") or "").strip().lower()
            expanded = str(record.get("expanded") or "").strip()
            if not abbr or not expanded or "_" not in abbr:
                continue
            phrase = abbr.replace("_", " ")
            db_phrases[phrase] = {
                "expanded": expanded,
                "source": "db",
                "confidence": 1.0,
            }
        # User-specific meanings remain stored for audit/retention, but are no
        # longer part of the effective normalization dataset. Only approved
        # shared meanings may influence a result.
        return LiveNormalizationData(
            abbreviations=abbreviations,
            dictionary_words=dictionary_words,
            approved_details=approved_details,
            phrase_overrides=phrase_overrides,
            db_phrases=db_phrases,
            mined_phrases=mined_phrases,
        )

    def _load_phrase_overrides(self, domain: str, db_ready: bool) -> Dict[str, dict]:
        phrase_overrides = dict(self.json_store.load_phrase_overrides())
        if not db_ready:
            return phrase_overrides

        repository = getattr(self, "phrase_override_repository", None)
        if repository is None:
            return phrase_overrides

        try:
            if not repository.is_ready():
                return phrase_overrides
            for phrase, expanded in repository.as_dict(domain).items():
                phrase_key = str(phrase or "").strip().lower()
                phrase_value = str(expanded or "").strip()
                if not phrase_key or not phrase_value:
                    continue
                phrase_overrides[phrase_key] = {
                    "expanded": phrase_value,
                    "source": "db_override",
                    "confidence": 1.0,
                }
        except Exception:  # pragma: no cover - best-effort DB enrichment
            logger.warning("Failed to load DB phrase overrides", exc_info=True)
        return phrase_overrides

    @classmethod
    def invalidate_live_normalization_cache(cls) -> None:
        with cls._live_data_cache_lock:
            cls._live_data_cache.clear()
            cls._live_data_cache_generation += 1
        with cls._shared_bootstrap_lock:
            cls._shared_bootstrap_cache.clear()
        with cls._pending_submit_lock:
            cls._pending_submit_cache.clear()

    @classmethod
    def live_normalization_cache_generation(cls) -> int:
        with cls._live_data_cache_lock:
            return cls._live_data_cache_generation

    def submit_pending_abbreviation(
        self,
        abbr: str,
        suggested: Optional[str] = None,
        submitted_by: Optional[str] = None,
        source: str = "runtime",
        domain: str = "general",
    ) -> dict:
        cleaned = abbr.strip().lower() if abbr else ""
        if not cleaned:
            return {"abbr": abbr, "status": "IGNORED", "pending_id": None, "has_suggested": False}

        # Live normalize fires on every keystroke, so the same unknown token was
        # re-submitted (one UPDATE + one audit-log row + one transaction) several
        # times a second. Replaying the previous payload for a few seconds keeps
        # the frontend contract intact — PendingNotice needs the full dict, not
        # just a count — while collapsing that write storm.
        cache_key = (self.settings, cleaned, domain)
        now = time.monotonic()
        with self._pending_submit_lock:
            cached = self._pending_submit_cache.get(cache_key)
            if cached and cached[1] > now:
                self._pending_submit_cache.move_to_end(cache_key)
                return dict(cached[0])

        result = self.repository.submit_pending_abbreviation(
            abbr=cleaned,
            suggested=suggested,
            submitted_by=submitted_by,
            source=source,
            domain=domain,
        )

        # Never cache a failure: the next keystroke should retry.
        if isinstance(result, dict) and result.get("pending_id"):
            with self._pending_submit_lock:
                self._pending_submit_cache[cache_key] = (
                    dict(result),
                    time.monotonic() + self._pending_submit_ttl_seconds,
                )
                self._pending_submit_cache.move_to_end(cache_key)
                while len(self._pending_submit_cache) > self._pending_submit_cache_max:
                    self._pending_submit_cache.popitem(last=False)
        return result

    def add_abbreviation_meaning(
        self,
        abbr: str,
        meaning: str,
        reviewer: str,
        domain: str = "general",
        source: str = "admin_manual",
        review_notes: Optional[str] = None,
        approve_immediately: bool = False,
    ) -> dict:
        cleaned_abbr = abbr.strip().lower()
        cleaned_meaning = meaning.strip()
        if not cleaned_abbr or not cleaned_meaning:
            return {
                "abbr": cleaned_abbr or abbr,
                "meaning": cleaned_meaning or meaning,
                "status": "IGNORED",
            }
        if not self.db_is_ready():
            return {
                "abbr": cleaned_abbr,
                "meaning": cleaned_meaning,
                "status": "DB_UNAVAILABLE",
            }

        approved_record = self.get_approved_abbreviation_details(cleaned_abbr, domain=domain)
        if approved_record:
            approved_meanings = [
                approved_record["expanded"],
                *approved_record.get("alternative_expansions", []),
            ]
            if cleaned_meaning in approved_meanings:
                return {
                    "abbr": cleaned_abbr,
                    "meaning": cleaned_meaning,
                    "status": "MEANING_ALREADY_APPROVED",
                    "approved": True,
                }

        submit_result = self.repository.submit_pending_abbreviation(
            abbr=cleaned_abbr,
            suggested=None,
            submitted_by=reviewer,
            source=source,
            domain=domain,
        )
        pending_id = submit_result.get("pending_id")
        if not pending_id:
            return {
                "abbr": cleaned_abbr,
                "meaning": cleaned_meaning,
                "status": submit_result.get("status", "PENDING_UNAVAILABLE"),
                "submit_status": submit_result.get("status"),
            }

        capture_result = self.repository.capture_pending_suggestion(
            pending_id=pending_id,
            suggested=cleaned_meaning,
            submitted_by=reviewer,
        )
        result = {
            "abbr": cleaned_abbr,
            "meaning": cleaned_meaning,
            "pending_id": pending_id,
            "submit_status": submit_result.get("status"),
            "capture_status": capture_result.get("status"),
            "status": capture_result.get("status"),
        }

        if approve_immediately:
            approval_result = self.repository.approve_pending_abbreviation(
                pending_id=pending_id,
                reviewer=reviewer,
                expanded=cleaned_meaning,
                review_notes=review_notes,
            )
            result["dictionary_sync"] = self.sync_approved_abbreviations_to_json()
            result["approval_status"] = approval_result.get("status")
            result["abbreviation_id"] = approval_result.get("abbreviation_id")
            result["status"] = approval_result.get("status", result["status"])

        return result

    def add_user_abbreviation_meaning(
        self,
        abbr: str,
        meaning: str,
        user_id: str,
        username: str,
        domain: str = "general",
    ) -> dict:
        cleaned_abbr = abbr.strip().lower()
        cleaned_meaning = meaning.strip()
        cleaned_user_id = user_id.strip()
        if not cleaned_abbr or not cleaned_meaning or not cleaned_user_id:
            return {
                "abbr": cleaned_abbr or abbr,
                "meaning": cleaned_meaning or meaning,
                "status": "IGNORED",
            }
        if not self.db_is_ready():
            return {
                "abbr": cleaned_abbr,
                "meaning": cleaned_meaning,
                "status": "DB_UNAVAILABLE",
            }

        approved_record = self.get_approved_abbreviation_details(cleaned_abbr, domain=domain)
        approved_abbreviation_id = approved_record.get("id") if approved_record else None
        approved_meanings = []
        if approved_record:
            approved_meanings = [
                approved_record["expanded"],
                *approved_record.get("alternative_expansions", []),
            ]
        globally_approved = cleaned_meaning in approved_meanings

        pending_id = None
        submit_status = "MEANING_ALREADY_APPROVED" if globally_approved else None
        capture_status = None
        if not globally_approved:
            submit_result = self.repository.submit_pending_abbreviation(
                abbr=cleaned_abbr,
                suggested=cleaned_meaning,
                submitted_by=username,
                source="user_personal",
                domain=domain,
            )
            submit_status = submit_result.get("status")
            pending_id = submit_result.get("pending_id")
            if pending_id:
                capture_result = self.repository.capture_pending_suggestion(
                    pending_id=pending_id,
                    suggested=cleaned_meaning,
                    submitted_by=username,
                )
                capture_status = capture_result.get("status")

        user_override = self.repository.upsert_user_abbreviation_override(
            user_id=cleaned_user_id,
            abbr=cleaned_abbr,
            meaning=cleaned_meaning,
            domain=domain,
            source="user_personal",
            pending_id=pending_id,
            approved_abbreviation_id=approved_abbreviation_id,
            updated_by=username,
        )
        if user_override.get("status") in {"DB_SCHEMA_MISSING", "DB_UNAVAILABLE"}:
            return {
                "abbr": cleaned_abbr,
                "meaning": cleaned_meaning,
                "status": user_override["status"],
                "pending_id": pending_id,
                "submit_status": submit_status,
                "capture_status": capture_status,
                "review_required": not globally_approved,
                "globally_approved": globally_approved,
                "user_override": user_override,
            }

        self.invalidate_live_normalization_cache()
        return {
            "abbr": cleaned_abbr,
            "meaning": cleaned_meaning,
            "status": "USER_MEANING_APPLIED",
            "pending_id": pending_id,
            "submit_status": submit_status,
            "capture_status": capture_status,
            "review_required": not globally_approved,
            "globally_approved": globally_approved,
            "user_override": user_override,
        }

    def get_approved_abbreviation_details(
        self, abbr: str, domain: str = "general"
    ) -> Optional[dict]:
        cleaned = abbr.strip().lower() if abbr else ""
        if not cleaned:
            return None
        if self.db_is_ready():
            record = self.repository.get_approved_abbreviation_details(
                cleaned, domain=domain
            )
            if record:
                return record

        for record in self.json_store.load_abbreviation_records():
            if (
                record.get("abbr", "").strip().lower() == cleaned
                and record.get("domain", "general") == domain
            ):
                return record
        return None

    def list_approved_abbreviations(
        self, abbr: Optional[str] = None, domain: Optional[str] = None
    ) -> List[dict]:
        records_by_key = {
            (
                record.get("abbr", "").strip().lower(),
                record.get("domain", "general"),
            ): record
            for record in self.json_store.load_abbreviation_records()
            if record.get("abbr")
        }
        if self.db_is_ready():
            records_by_key.update(
                {
                    (
                        record.get("abbr", "").strip().lower(),
                        record.get("domain", "general"),
                    ): record
                    for record in self.repository.list_approved_abbreviations()
                    if record.get("abbr")
                }
            )

        records = sorted(
            records_by_key.values(),
            key=lambda record: (
                str(record.get("abbr") or ""),
                str(record.get("domain") or "general"),
            ),
        )
        cleaned = abbr.strip().lower() if abbr else ""
        return [
            record
            for record in records
            if (not cleaned or record.get("abbr", "").strip().lower() == cleaned)
            and (domain is None or record.get("domain", "general") == domain)
        ]

    def list_pending_abbreviations(self, status: str = "PENDING") -> List[dict]:
        if not self.db_is_ready():
            return []
        return self.repository.list_pending_abbreviations(status=status)

    def get_pending_abbreviation_detail(self, pending_id: str) -> Optional[dict]:
        cleaned = pending_id.strip()
        if not cleaned or not self.db_is_ready():
            return None
        return self.repository.get_pending_abbreviation_detail(cleaned)

    def capture_pending_suggestion(
        self,
        pending_id: str,
        suggested: str,
        submitted_by: Optional[str] = None,
    ) -> dict:
        cleaned_pending_id = pending_id.strip()
        cleaned_suggested = suggested.strip()
        if not cleaned_pending_id or not cleaned_suggested:
            return {"pending_id": cleaned_pending_id or pending_id, "status": "IGNORED"}

        return self.repository.capture_pending_suggestion(
            pending_id=cleaned_pending_id,
            suggested=cleaned_suggested,
            submitted_by=submitted_by,
        )

    def approve_pending_abbreviation(
        self,
        pending_id: str,
        reviewer: str,
        expanded: Optional[str] = None,
        review_notes: Optional[str] = None,
    ) -> dict:
        result = self.repository.approve_pending_abbreviation(
            pending_id=pending_id,
            reviewer=reviewer,
            expanded=expanded,
            review_notes=review_notes,
        )
        result["dictionary_sync"] = self.sync_approved_abbreviations_to_json()
        return result

    def reject_pending_abbreviation(
        self, pending_id: str, reviewer: str, review_notes: Optional[str] = None
    ) -> dict:
        return self.repository.reject_pending_abbreviation(
            pending_id=pending_id,
            reviewer=reviewer,
            review_notes=review_notes,
        )

    def save_approved_abbreviation(
        self,
        abbr: str,
        expanded: str,
        reviewer: str,
        alternative_expansions: Optional[List[str]] = None,
        domain: str = "general",
        source: str = "admin_dictionary",
    ) -> dict:
        cleaned_abbr = abbr.strip().lower()
        cleaned_expanded = expanded.strip()
        if not cleaned_abbr or not cleaned_expanded:
            raise ValueError("INVALID_ABBREVIATION_PAYLOAD")
        if not self.db_is_ready():
            raise RuntimeError("SQL Server chua san sang.")

        normalized_alternatives = self._normalize_meanings(alternative_expansions or [])
        normalized_alternatives = [
            meaning for meaning in normalized_alternatives if meaning != cleaned_expanded
        ]

        self.repository.bulk_upsert_abbreviations(
            [
                {
                    "abbr": cleaned_abbr,
                    "expanded": cleaned_expanded,
                    "alternative_expansions": normalized_alternatives,
                    "domain": domain,
                    "source": source,
                }
            ],
            approved_by=reviewer,
            # An admin editing the dictionary IS authoritative: the meanings they
            # submit replace the stored list. Seeding (the default) merges.
            replace_alternatives=True,
        )
        sync = self.sync_approved_abbreviations_to_json()
        try:
            record = self.repository.get_approved_abbreviation_details(cleaned_abbr, domain=domain)
            if not record:
                raise RuntimeError("Dictionary record unavailable after commit")
        except Exception as exc:
            raise DictionaryWriteCommittedError("SQL saved; read-back unavailable") from exc
        return {**record, "dictionary_sync": sync}

    def delete_approved_abbreviation(self, abbr: str, domain: str, reviewer: str) -> dict:
        if not self.db_is_ready():
            raise RuntimeError("SQL Server chua san sang.")
        deleted = self.repository.deactivate_abbreviation(abbr, domain, reviewer)
        if not deleted:
            raise KeyError("NOT_FOUND")
        sync = self.sync_approved_abbreviations_to_json()
        return {"abbr": abbr.strip().lower(), "domain": domain, "deleted": True, "dictionary_sync": sync}

    def sync_approved_abbreviations_to_json(self) -> object:
        try:
            return self._export_and_publish_dictionary()
        except Exception as exc:
            raise DictionaryWriteCommittedError("SQL saved; shared revision unavailable") from exc

    def _export_and_publish_dictionary(self) -> dict:
        state = DictionaryState(self.settings.data_dir)
        self.invalidate_live_normalization_cache()
        with state.connection(write=True) as connection:
            status = "synced"
            try:
                if not self.db_is_ready():
                    raise RuntimeError("SQL unavailable during export")
                approved = self.repository.list_approved_abbreviations()
                self.json_store.export_approved_abbreviations(approved)
            except Exception:
                status = "export_failed"
                logger.exception("Dictionary SQL write retained; JSON export failed")
            result = state.advance(connection, status)
        return result

    def seed_from_json(self) -> dict:
        self.invalidate_live_normalization_cache()
        abbreviations_payload = self._load_seed_abbreviations()
        dictionary_payload = self._load_seed_dictionaries()
        result = {
            "abbreviations_seeded": self.repository.bulk_upsert_abbreviations(
                abbreviations_payload
            ),
            "dictionary_words_seeded": sum(
                self.repository.bulk_upsert_dictionary_words(name, words)
                for name, words in dictionary_payload.items()
            ),
        }
        self.sync_approved_abbreviations_to_json()
        return result

    def _load_seed_abbreviations(self) -> List[dict]:
        path = self.json_store.abbreviations_path
        if not path.exists():
            path = self.json_store.legacy_abbreviations_path
        with path.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
        return payload.get("abbreviations", [])

    def _load_seed_dictionaries(self) -> Dict[str, List[str]]:
        dictionary_payload: Dict[str, List[str]] = {}
        candidates = sorted(self.json_store.dictionary_dir.glob("*.json"))
        if not candidates:
            candidates = sorted(self.json_store.legacy_dictionary_dir.glob("Viet*.json"))

        for path in candidates:
            with path.open("r", encoding="utf-8-sig") as handle:
                payload = json.load(handle)
            dictionary_payload[path.stem] = [
                item["word"] for item in payload.get("words", []) if item.get("word")
            ]
        return dictionary_payload

    @staticmethod
    def _normalize_meanings(meanings: List[str]) -> List[str]:
        normalized: List[str] = []
        for meaning in meanings:
            cleaned = meaning.strip()
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)
        return normalized

    @classmethod
    def _merge_user_overrides(
        cls,
        abbreviations: Dict[str, str],
        approved_details: Dict[str, dict],
        user_overrides: List[dict],
    ) -> None:
        for override in user_overrides:
            abbr = str(override.get("abbr") or "").strip().lower()
            expanded = str(override.get("expanded") or "").strip()
            if not abbr or not expanded:
                continue

            base = approved_details.get(abbr, {})
            alternatives = cls._normalize_meanings(
                [
                    *override.get("alternative_expansions", []),
                    str(base.get("expanded") or ""),
                    *base.get("alternative_expansions", []),
                ]
            )
            alternatives = [meaning for meaning in alternatives if meaning != expanded]

            user_detail = dict(base)
            user_detail.update(override)
            user_detail["abbr"] = abbr
            user_detail["expanded"] = expanded
            user_detail["alternative_expansions"] = alternatives
            user_detail["source"] = override.get("source") or "user_personal"
            user_detail["user_override"] = True

            abbreviations[abbr] = expanded
            approved_details[abbr] = user_detail
