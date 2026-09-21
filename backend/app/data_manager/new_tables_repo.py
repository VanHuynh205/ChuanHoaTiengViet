"""Repositories for the 4 new tables added in schema v2 (2026-05-23).

- SessionRepository      -- dbo.user_sessions (JWT revoke / server-side logout)
- PreferencesRepository   -- dbo.user_preferences (persist variant/UI choices)
- PhraseOverrideRepository -- dbo.phrase_overrides (phrase overrides in DB)
- UsageStatsRepository    -- dbo.abbreviation_usage_stats (analytics)

All follow the same pattern as UserRepository / HistoryRepository:
parameterized queries via sqlalchemy.text(), Settings-based session factory.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import Counter
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Iterable
from weakref import WeakKeyDictionary

from app.config import Settings
from app.data_manager.db import get_session_factory

text: Any

try:
    from sqlalchemy import text
except ImportError:  # pragma: no cover
    text = None

logger = logging.getLogger(__name__)

# How long a "table is missing" answer stays cached. Positive answers are
# cached forever (a table never disappears mid-process); negative answers expire
# so applying init_schema.sql to a running deployment takes effect without a
# restart.
_TABLE_MISSING_TTL_SECONDS = 60.0

_table_cache: "WeakKeyDictionary[Any, dict[str, tuple[bool, float]]]" = WeakKeyDictionary()
_table_cache_lock = Lock()


def probe_table(session_factory: Any, table_name: str) -> bool | None:
    """Cached ``OBJECT_ID`` probe.

    Returns ``True`` (table present), ``False`` (table genuinely absent) or
    ``None`` (**unknown** — the probe itself failed). Callers must treat
    ``None`` differently from ``False``: "the table was never deployed" and "the
    database is broken right now" have opposite safe defaults.

    Repositories are constructed per request (FastAPI ``Depends``), so without a
    process-level cache every authenticated call paid an extra round-trip just
    to ask whether ``dbo.user_sessions`` exists — on an endpoint that fires once
    per keystroke. Results are keyed by the session factory, which
    ``get_session_factory`` already memoises per ``Settings``.
    """
    if not session_factory or text is None:
        return False

    now = time.monotonic()
    with _table_cache_lock:
        cached = _table_cache.get(session_factory, {}).get(table_name)
    if cached is not None:
        exists, expires_at = cached
        # Positive answers never expire (a table does not vanish mid-process);
        # negative ones do, so applying init_schema.sql to a running deployment
        # takes effect without a restart.
        if exists or expires_at > now:
            return exists

    try:
        with session_factory() as session:
            exists = _table_exists(session, table_name)
    except Exception:
        logger.warning("Failed to probe table dbo.%s", table_name, exc_info=True)
        return None

    with _table_cache_lock:
        try:
            _table_cache.setdefault(session_factory, {})[table_name] = (
                exists,
                float("inf") if exists else now + _TABLE_MISSING_TTL_SECONDS,
            )
        except TypeError:  # pragma: no cover - non-weakref-able factory in tests
            pass
    return exists


def _table_is_available(session_factory: Any, table_name: str) -> bool:
    """``True`` only when the table is known to exist."""
    return probe_table(session_factory, table_name) is True


def reset_table_cache() -> None:
    """Clear the schema probe cache — for tests and post-migration hooks."""
    with _table_cache_lock:
        _table_cache.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_token(token: str) -> str:
    """SHA-256 hash of a JWT token for storage (never store raw tokens)."""
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def _table_exists(session: Any, table_name: str) -> bool:
    result = session.execute(
        text("SELECT OBJECT_ID(:tbl, N'U')"),
        {"tbl": f"dbo.{table_name}"},
    ).scalar()
    return result is not None


def _coerce_datetime(value: object) -> object:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).replace(tzinfo=None)
    return value


# =========================================================================
# 1. SessionRepository (user_sessions)
# =========================================================================

class SessionRepository:
    """Manage JWT sessions for server-side token revocation."""

    _TABLE = "user_sessions"

    def __init__(self, settings: Settings) -> None:
        self.session_factory = get_session_factory(settings)

    def is_ready(self) -> bool:
        return self._has_session_table()

    def _has_session_table(self) -> bool:
        return _table_is_available(self.session_factory, self._TABLE)

    def create_session(
        self,
        user_id: str,
        token: str,
        expires_at: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict | None:
        if not self.session_factory or text is None:
            return None
        if not self._has_session_table():
            return None
        query = text("""
            INSERT INTO dbo.user_sessions
                (user_id, token_hash, ip_address, user_agent, expires_at)
            OUTPUT
                CAST(inserted.id AS NVARCHAR(36)) AS id,
                CAST(inserted.user_id AS NVARCHAR(36)) AS user_id,
                inserted.issued_at,
                inserted.expires_at,
                inserted.is_active
            VALUES
                (:user_id, :token_hash, :ip_address, :user_agent, :expires_at)
        """)
        try:
            with self.session_factory() as session:
                row = session.execute(query, {
                    "user_id": user_id,
                    "token_hash": _hash_token(token),
                    "ip_address": ip_address,
                    "user_agent": (user_agent or "")[:500],
                    "expires_at": _coerce_datetime(expires_at),
                }).mappings().first()
                session.commit()
                return dict(row) if row else None
        except Exception:
            logger.warning("Failed to create user session", exc_info=True)
            return None

    def is_token_valid(self, token: str) -> bool:
        """Check if a token is active and not revoked/expired.

        Deliberately asymmetric: when the ``user_sessions`` table does not exist
        at all we allow the request through, because revocation was never
        recorded for anyone and blocking would lock every user out of a schema-v1
        deployment. But once the table exists, a *query failure* must NOT grant
        access — that path used to let a revoked token back in for as long as the
        database was struggling.
        """
        if not self.session_factory or text is None:
            return True  # no session store configured: nothing was ever revoked
        table_state = probe_table(self.session_factory, self._TABLE)
        if table_state is None:
            logger.warning("Session table probe failed; rejecting token (fail-closed).")
            return False
        if table_state is False:
            return True
        query = text("""
            SELECT 1 FROM dbo.user_sessions
            WHERE token_hash = :token_hash
              AND is_active = 1
              AND revoked_at IS NULL
              AND expires_at > SYSUTCDATETIME()
        """)
        try:
            with self.session_factory() as session:
                result = session.execute(query, {
                    "token_hash": _hash_token(token),
                }).scalar()
                return result is not None
        except Exception:
            logger.warning(
                "Session validation query failed; rejecting token (fail-closed).",
                exc_info=True,
            )
            return False

    def revoke_token(self, token: str, reason: str = "logout") -> bool:
        if not self.session_factory or text is None:
            return False
        if not self._has_session_table():
            return False
        query = text("""
            UPDATE dbo.user_sessions
            SET is_active = 0,
                revoked_at = SYSUTCDATETIME(),
                revoke_reason = :reason
            WHERE token_hash = :token_hash
              AND is_active = 1
        """)
        try:
            with self.session_factory() as session:
                result = session.execute(query, {
                    "token_hash": _hash_token(token),
                    "reason": reason[:100],
                })
                session.commit()
                return result.rowcount > 0
        except Exception:
            logger.warning("Failed to revoke token", exc_info=True)
            return False

    def revoke_all_user_sessions(self, user_id: str, reason: str = "logout_all") -> int:
        if not self.session_factory or text is None:
            return 0
        if not self._has_session_table():
            return 0
        query = text("""
            UPDATE dbo.user_sessions
            SET is_active = 0,
                revoked_at = SYSUTCDATETIME(),
                revoke_reason = :reason
            WHERE user_id = :user_id
              AND is_active = 1
        """)
        try:
            with self.session_factory() as session:
                result = session.execute(query, {
                    "user_id": user_id,
                    "reason": reason[:100],
                })
                session.commit()
                return result.rowcount
        except Exception:
            logger.warning("Failed to revoke all sessions for user %s", user_id, exc_info=True)
            # Re-raise so the route can answer 503 instead of pretending every
            # session was revoked while a database blip left them all active.
            raise

    def get_active_sessions(self, user_id: str) -> list[dict]:
        if not self.session_factory or text is None:
            return []
        if not self._has_session_table():
            return []
        query = text("""
            SELECT
                CAST(id AS NVARCHAR(36)) AS id,
                ip_address,
                user_agent,
                issued_at,
                expires_at,
                last_activity_at
            FROM dbo.user_sessions
            WHERE user_id = :user_id
              AND is_active = 1
              AND revoked_at IS NULL
              AND expires_at > SYSUTCDATETIME()
            ORDER BY issued_at DESC
        """)
        try:
            with self.session_factory() as session:
                rows = session.execute(query, {"user_id": user_id}).mappings().all()
                return [dict(r) for r in rows]
        except Exception:
            return []

    def cleanup_expired(self) -> int:
        if not self.session_factory or text is None:
            return 0
        if not self._has_session_table():
            return 0
        query = text("""
            UPDATE dbo.user_sessions
            SET is_active = 0,
                revoke_reason = N'expired'
            WHERE is_active = 1
              AND expires_at < SYSUTCDATETIME()
        """)
        try:
            with self.session_factory() as session:
                result = session.execute(query)
                session.commit()
                return result.rowcount
        except Exception:
            return 0


# =========================================================================
# 2. PreferencesRepository (user_preferences)
# =========================================================================

class PreferencesRepository:
    """CRUD for user preferences (variant choices, UI settings)."""

    def __init__(self, settings: Settings) -> None:
        self.session_factory = get_session_factory(settings)

    def is_ready(self) -> bool:
        return _table_is_available(self.session_factory, "user_preferences")

    def get_all(self, user_id: str, category: str | None = None) -> list[dict]:
        if not self.session_factory or text is None:
            return []
        if category:
            query = text("""
                SELECT preference_key, preference_value, category, updated_at
                FROM dbo.user_preferences
                WHERE user_id = :user_id AND category = :category
                ORDER BY preference_key
            """)
            params = {"user_id": user_id, "category": category}
        else:
            query = text("""
                SELECT preference_key, preference_value, category, updated_at
                FROM dbo.user_preferences
                WHERE user_id = :user_id
                ORDER BY category, preference_key
            """)
            params = {"user_id": user_id}
        try:
            with self.session_factory() as session:
                rows = session.execute(query, params).mappings().all()
                return [dict(r) for r in rows]
        except Exception:
            return []

    def get(self, user_id: str, key: str) -> str | None:
        if not self.session_factory or text is None:
            return None
        query = text("""
            SELECT preference_value
            FROM dbo.user_preferences
            WHERE user_id = :user_id AND preference_key = :key
        """)
        try:
            with self.session_factory() as session:
                return session.execute(query, {
                    "user_id": user_id,
                    "key": key,
                }).scalar()
        except Exception:
            return None

    def set(self, user_id: str, key: str, value: str, category: str = "general") -> bool:
        """Upsert a preference (MERGE pattern for SQL Server)."""
        if not self.session_factory or text is None:
            return False
        query = text("""
            MERGE dbo.user_preferences WITH (HOLDLOCK) AS target
            USING (SELECT :user_id AS user_id, :key AS preference_key) AS source
            ON target.user_id = source.user_id
               AND target.preference_key = source.preference_key
            WHEN MATCHED THEN
                UPDATE SET
                    preference_value = :value,
                    category = :category,
                    updated_at = SYSUTCDATETIME()
            WHEN NOT MATCHED THEN
                INSERT (user_id, preference_key, preference_value, category)
                VALUES (:user_id, :key, :value, :category);
        """)
        try:
            with self.session_factory() as session:
                session.execute(query, {
                    "user_id": user_id,
                    "key": key,
                    "value": value,
                    "category": category,
                })
                session.commit()
                return True
        except Exception:
            logger.warning("Failed to set preference %s for user %s", key, user_id, exc_info=True)
            return False

    def delete(self, user_id: str, key: str) -> bool:
        if not self.session_factory or text is None:
            return False
        query = text("""
            DELETE FROM dbo.user_preferences
            WHERE user_id = :user_id AND preference_key = :key
        """)
        try:
            with self.session_factory() as session:
                result = session.execute(query, {"user_id": user_id, "key": key})
                session.commit()
                return result.rowcount > 0
        except Exception:
            return False


# =========================================================================
# 3. PhraseOverrideRepository (phrase_overrides)
# =========================================================================

class PhraseOverrideRepository:
    """CRUD for phrase overrides in DB (replaces phrase_overrides.json for admin)."""

    def __init__(self, settings: Settings) -> None:
        self.session_factory = get_session_factory(settings)

    def is_ready(self) -> bool:
        return _table_is_available(self.session_factory, "phrase_overrides")

    def get_active(self, domain: str | None = None) -> list[dict]:
        if not self.session_factory or text is None:
            return []
        if domain:
            query = text("""
                SELECT
                    CAST(id AS NVARCHAR(36)) AS id,
                    phrase_key, phrase_value, domain, source,
                    priority, notes, created_by, updated_at
                FROM dbo.phrase_overrides
                WHERE is_active = 1 AND approved = 1 AND domain = :domain
                ORDER BY priority DESC, phrase_key
            """)
            params = {"domain": domain}
        else:
            query = text("""
                SELECT
                    CAST(id AS NVARCHAR(36)) AS id,
                    phrase_key, phrase_value, domain, source,
                    priority, notes, created_by, updated_at
                FROM dbo.phrase_overrides
                WHERE is_active = 1 AND approved = 1
                ORDER BY domain, priority DESC, phrase_key
            """)
            params = {}
        try:
            with self.session_factory() as session:
                rows = session.execute(query, params).mappings().all()
                return [dict(r) for r in rows]
        except Exception:
            return []

    def create(
        self,
        phrase_key: str,
        phrase_value: str,
        domain: str = "general",
        source: str = "manual",
        priority: int = 0,
        notes: str | None = None,
        created_by: str | None = None,
    ) -> dict | None:
        if not self.session_factory or text is None:
            return None
        query = text("""
            INSERT INTO dbo.phrase_overrides
                (phrase_key, phrase_value, domain, source, priority, notes, created_by)
            OUTPUT
                CAST(inserted.id AS NVARCHAR(36)) AS id,
                inserted.phrase_key, inserted.phrase_value,
                inserted.domain, inserted.priority, inserted.created_at
            VALUES
                (:phrase_key, :phrase_value, :domain, :source, :priority, :notes, :created_by)
        """)
        try:
            with self.session_factory() as session:
                row = session.execute(query, {
                    "phrase_key": phrase_key,
                    "phrase_value": phrase_value,
                    "domain": domain,
                    "source": source,
                    "priority": priority,
                    "notes": notes,
                    "created_by": created_by,
                }).mappings().first()
                session.commit()
                return dict(row) if row else None
        except Exception:
            logger.warning("Failed to create phrase override", exc_info=True)
            return None

    def update(
        self,
        override_id: str,
        phrase_value: str | None = None,
        priority: int | None = None,
        notes: str | None = None,
        updated_by: str | None = None,
    ) -> bool:
        if not self.session_factory or text is None:
            return False
        query = text("""
            UPDATE dbo.phrase_overrides
            SET updated_at = SYSUTCDATETIME(),
                phrase_value = CASE
                    WHEN :has_phrase_value = 1 THEN :phrase_value
                    ELSE phrase_value
                END,
                priority = CASE
                    WHEN :has_priority = 1 THEN :priority
                    ELSE priority
                END,
                notes = CASE
                    WHEN :has_notes = 1 THEN :notes
                    ELSE notes
                END,
                updated_by = CASE
                    WHEN :has_updated_by = 1 THEN :updated_by
                    ELSE updated_by
                END
            WHERE id = :id AND is_active = 1
        """)
        params = {
            "id": override_id,
            "phrase_value": phrase_value,
            "has_phrase_value": 1 if phrase_value is not None else 0,
            "priority": priority,
            "has_priority": 1 if priority is not None else 0,
            "notes": notes,
            "has_notes": 1 if notes is not None else 0,
            "updated_by": updated_by,
            "has_updated_by": 1 if updated_by is not None else 0,
        }
        try:
            with self.session_factory() as session:
                result = session.execute(query, params)
                session.commit()
                return result.rowcount > 0
        except Exception:
            return False

    def soft_delete(self, override_id: str, updated_by: str | None = None) -> bool:
        if not self.session_factory or text is None:
            return False
        query = text("""
            UPDATE dbo.phrase_overrides
            SET is_active = 0,
                updated_at = SYSUTCDATETIME(),
                updated_by = :updated_by
            WHERE id = :id AND is_active = 1
        """)
        try:
            with self.session_factory() as session:
                result = session.execute(query, {
                    "id": override_id,
                    "updated_by": updated_by,
                })
                session.commit()
                return result.rowcount > 0
        except Exception:
            return False

    def as_dict(self, domain: str | None = None) -> dict[str, str]:
        """Return active overrides as {phrase_key: phrase_value} for pipeline use."""
        overrides = self.get_active(domain)
        return {o["phrase_key"]: o["phrase_value"] for o in overrides}


# =========================================================================
# 4. UsageStatsRepository (abbreviation_usage_stats)
# =========================================================================

class UsageStatsRepository:
    """Record and query abbreviation usage statistics."""

    def __init__(self, settings: Settings) -> None:
        self.session_factory = get_session_factory(settings)

    def is_ready(self) -> bool:
        return _table_is_available(self.session_factory, "abbreviation_usage_stats")

    # ``WITH (HOLDLOCK)`` is required for a correct MERGE upsert on SQL Server:
    # without it two concurrent MERGEs can both take the NOT MATCHED branch and
    # collide on UX_abbreviation_usage_stats_daily.
    _MERGE_USAGE_SQL = """
            MERGE dbo.abbreviation_usage_stats WITH (HOLDLOCK) AS target
            USING (
                SELECT
                    :abbr AS abbr,
                    :expanded_chosen AS expanded_chosen,
                    CAST(SYSUTCDATETIME() AS DATE) AS usage_date,
                    :source_kind AS source_kind
            ) AS source
            ON target.abbr = source.abbr
               AND target.expanded_chosen = source.expanded_chosen
               AND target.usage_date = source.usage_date
               AND target.source_kind = source.source_kind
            WHEN MATCHED THEN
                UPDATE SET
                    usage_count = target.usage_count + :increment,
                    updated_at = SYSUTCDATETIME()
            WHEN NOT MATCHED THEN
                INSERT (abbreviation_id, abbr, expanded_chosen, source_kind, usage_count)
                VALUES (:abbreviation_id, :abbr, :expanded_chosen, :source_kind, :increment);
        """

    def record_usage(
        self,
        abbr: str,
        expanded_chosen: str,
        source_kind: str = "live",
        abbreviation_id: str | None = None,
        increment: int = 1,
    ) -> bool:
        """Increment daily usage counter (upsert on unique daily key)."""
        if not self.session_factory or text is None:
            return False
        query = text(self._MERGE_USAGE_SQL)
        try:
            with self.session_factory() as session:
                session.execute(query, {
                    "abbr": abbr[:100],
                    "expanded_chosen": expanded_chosen[:500],
                    "source_kind": source_kind[:50],
                    "abbreviation_id": abbreviation_id,
                    "increment": max(1, int(increment)),
                })
                session.commit()
                return True
        except Exception:
            # Telemetry must never fail normalization, but silence used to hide
            # sustained data loss — log at debug so it is at least diagnosable.
            logger.debug("Failed to record abbreviation usage for %r", abbr, exc_info=True)
            return False

    def record_usage_bulk(
        self,
        usages: Iterable[tuple[str, str]],
        source_kind: str = "live",
        max_rows: int = 200,
    ) -> int:
        """Record many ``(abbr, expanded)`` pairs in ONE transaction.

        The per-span variant opened a fresh session and transaction for every
        expanded abbreviation, so a single long paste produced over a thousand
        round-trips that all contended on the same few rows. Counting duplicates
        up-front also fixes the double counting that happened when the same span
        appeared many times in one request.

        Returns the number of distinct rows written.
        """
        if not self.session_factory or text is None:
            return 0

        counts: Counter[tuple[str, str]] = Counter()
        for abbr, expanded in usages:
            cleaned_abbr = str(abbr or "").strip()[:100]
            cleaned_expanded = str(expanded or "").strip()[:500]
            if cleaned_abbr and cleaned_expanded:
                counts[(cleaned_abbr, cleaned_expanded)] += 1
        if not counts:
            return 0

        # Guard against a pathological input producing an unbounded statement
        # batch; the most-used entries are the ones worth keeping.
        rows = counts.most_common(max(1, max_rows))
        query = text(self._MERGE_USAGE_SQL)
        params = [
            {
                "abbr": abbr,
                "expanded_chosen": expanded,
                "source_kind": source_kind[:50],
                "abbreviation_id": None,
                "increment": count,
            }
            for (abbr, expanded), count in rows
        ]
        try:
            with self.session_factory() as session:
                session.execute(query, params)
                session.commit()
                return len(params)
        except Exception:
            logger.debug("Failed to bulk-record abbreviation usage", exc_info=True)
            return 0

    def get_top_abbreviations(
        self,
        days: int = 30,
        limit: int = 50,
    ) -> list[dict]:
        if not self.session_factory or text is None:
            return []
        query = text("""
            SELECT TOP(:limit)
                abbr,
                expanded_chosen,
                SUM(usage_count) AS total_count,
                MAX(usage_date) AS last_used,
                COUNT(DISTINCT usage_date) AS active_days
            FROM dbo.abbreviation_usage_stats
            WHERE usage_date >= DATEADD(DAY, -:days, CAST(SYSUTCDATETIME() AS DATE))
            GROUP BY abbr, expanded_chosen
            ORDER BY total_count DESC
        """)
        try:
            with self.session_factory() as session:
                rows = session.execute(query, {
                    "limit": limit,
                    "days": days,
                }).mappings().all()
                return [dict(r) for r in rows]
        except Exception:
            logger.warning("Failed to query top abbreviation usage", exc_info=True)
            return []

    def get_daily_stats(self, days: int = 7) -> list[dict]:
        if not self.session_factory or text is None:
            return []
        query = text("""
            SELECT
                usage_date,
                COUNT(DISTINCT abbr) AS unique_abbreviations,
                SUM(usage_count) AS total_uses
            FROM dbo.abbreviation_usage_stats
            WHERE usage_date >= DATEADD(DAY, -:days, CAST(SYSUTCDATETIME() AS DATE))
            GROUP BY usage_date
            ORDER BY usage_date DESC
        """)
        try:
            with self.session_factory() as session:
                rows = session.execute(query, {"days": days}).mappings().all()
                return [dict(r) for r in rows]
        except Exception:
            logger.warning("Failed to query daily usage stats", exc_info=True)
            return []
