from __future__ import annotations

import json
import time
from threading import Lock
from typing import Any, Callable, ClassVar, Dict, Iterable, List, Optional, Set, Tuple

from app.config import Settings
from app.data_manager.db import get_session_factory

text: Any

try:
    from sqlalchemy import text
except ImportError:  # pragma: no cover - optional dependency in early setup
    text = None


def _missing_session_factory() -> Any:
    raise RuntimeError("SQLAlchemy session factory is not available.")


class AbbreviationRepository:
    def deactivate_abbreviation(self, abbr: str, domain: str = "general", reviewer: str = "admin") -> bool:
        if not self.is_ready():
            return False
        with self.session_factory() as session:
            result = session.execute(text("""
                UPDATE dbo.abbreviations SET is_active = 0, updated_at = SYSUTCDATETIME(), approved_by = :reviewer
                WHERE abbr = :abbr AND domain = :domain AND is_active = 1
            """), {"abbr": abbr.strip().lower(), "domain": domain, "reviewer": reviewer})
            session.commit()
            return result.rowcount > 0
    # (exists, expires_at) — a negative answer expires so a migration applied to
    # a running process is picked up without a restart.
    _schema_table_cache: ClassVar[Dict[Tuple[object, str], Tuple[bool, float]]] = {}
    _schema_table_cache_lock: ClassVar[Lock] = Lock()
    _USER_OVERRIDE_TABLE = "dbo.user_abbreviation_overrides"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        session_factory = get_session_factory(settings)
        self._has_session_factory = session_factory is not None
        self.session_factory: Callable[[], Any] = session_factory or _missing_session_factory

    def is_ready(self) -> bool:
        has_session_factory = getattr(
            self,
            "_has_session_factory",
            getattr(self, "session_factory", None) is not None,
        )
        return bool(has_session_factory) and text is not None

    def get_approved_abbreviation_map(self) -> Dict[str, str]:
        rows = self.list_approved_abbreviations()
        return {row["abbr"].lower(): row["expanded"] for row in rows}

    def list_approved_abbreviations(self) -> List[dict]:
        if not self.is_ready():
            return []

        query = text("""
            SELECT
                CAST(id AS NVARCHAR(36)) AS id,
                abbr,
                expanded,
                alternative_expansions_json,
                domain,
                source,
                CONVERT(NVARCHAR(33), created_at, 126) AS created_at,
                approved_by
            FROM dbo.abbreviations
            WHERE is_active = 1 AND approved = 1
            ORDER BY abbr
            """)
        with self.session_factory() as session:
            return [
                self._normalize_approved_record(dict(row))
                for row in session.execute(query).mappings().all()
            ]

    def get_approved_abbreviation_details(
        self, abbr: str, domain: str = "general"
    ) -> Optional[dict]:
        if not self.is_ready():
            return None

        query = text("""
            SELECT
                CAST(id AS NVARCHAR(36)) AS id,
                abbr,
                expanded,
                alternative_expansions_json,
                domain,
                source,
                CONVERT(NVARCHAR(33), created_at, 126) AS created_at,
                approved_by
            FROM dbo.abbreviations
            WHERE is_active = 1 AND approved = 1 AND abbr = :abbr AND domain = :domain
            """)
        with self.session_factory() as session:
            record = session.execute(query, {"abbr": abbr, "domain": domain}).mappings().first()
            return self._normalize_approved_record(dict(record)) if record else None

    def get_dictionary_words(self) -> Set[str]:
        if not self.is_ready():
            return set()

        query = text("""
            SELECT word
            FROM dbo.dictionary_entries
            WHERE is_active = 1 AND approved = 1
            """)
        with self.session_factory() as session:
            return {row["word"].lower() for row in session.execute(query).mappings().all()}

    def list_user_abbreviation_overrides(
        self,
        user_id: str,
        domain: str = "general",
    ) -> List[dict]:
        if not self.is_ready():
            return []
        if not self._table_exists(self._USER_OVERRIDE_TABLE):
            return []

        query = text("""
            SELECT
                CAST(id AS NVARCHAR(36)) AS id,
                CAST(user_id AS NVARCHAR(36)) AS user_id,
                abbr,
                expanded,
                alternative_expansions_json,
                domain,
                source,
                CAST(pending_id AS NVARCHAR(36)) AS pending_id,
                CAST(approved_abbreviation_id AS NVARCHAR(36)) AS approved_abbreviation_id,
                usage_count,
                CONVERT(NVARCHAR(33), created_at, 126) AS created_at,
                CONVERT(NVARCHAR(33), updated_at, 126) AS updated_at
            FROM dbo.user_abbreviation_overrides
            WHERE user_id = TRY_CONVERT(UNIQUEIDENTIFIER, :user_id)
              AND domain = :domain
              AND is_active = 1
            ORDER BY updated_at DESC
            """)
        try:
            with self.session_factory() as session:
                return [
                    self._normalize_user_override_record(dict(row))
                    for row in session.execute(
                        query,
                        {"user_id": user_id, "domain": domain},
                    )
                    .mappings()
                    .all()
                ]
        except Exception as exc:
            if self._is_missing_table_error(exc, self._USER_OVERRIDE_TABLE):
                self._set_table_exists(self._USER_OVERRIDE_TABLE, False)
                return []
            raise

    def upsert_user_abbreviation_override(
        self,
        user_id: str,
        abbr: str,
        meaning: str,
        domain: str = "general",
        source: str = "user_personal",
        pending_id: Optional[str] = None,
        approved_abbreviation_id: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> dict:
        if not self.is_ready():
            return {"abbr": abbr, "expanded": meaning, "status": "DB_UNAVAILABLE"}
        if not self._table_exists(self._USER_OVERRIDE_TABLE):
            return {"abbr": abbr, "expanded": meaning, "status": "DB_SCHEMA_MISSING"}

        select_existing = text("""
            SELECT
                CAST(id AS NVARCHAR(36)) AS id,
                expanded,
                alternative_expansions_json
            FROM dbo.user_abbreviation_overrides
            WHERE user_id = TRY_CONVERT(UNIQUEIDENTIFIER, :user_id)
              AND abbr = :abbr
              AND domain = :domain
              AND is_active = 1
            """)
        select_saved = text("""
            SELECT
                CAST(id AS NVARCHAR(36)) AS id,
                CAST(user_id AS NVARCHAR(36)) AS user_id,
                abbr,
                expanded,
                alternative_expansions_json,
                domain,
                source,
                CAST(pending_id AS NVARCHAR(36)) AS pending_id,
                CAST(approved_abbreviation_id AS NVARCHAR(36)) AS approved_abbreviation_id,
                usage_count,
                CONVERT(NVARCHAR(33), created_at, 126) AS created_at,
                CONVERT(NVARCHAR(33), updated_at, 126) AS updated_at
            FROM dbo.user_abbreviation_overrides
            WHERE user_id = TRY_CONVERT(UNIQUEIDENTIFIER, :user_id)
              AND abbr = :abbr
              AND domain = :domain
              AND is_active = 1
            """)
        insert_stmt = text("""
            INSERT INTO dbo.user_abbreviation_overrides (
                id,
                user_id,
                abbr,
                expanded,
                alternative_expansions_json,
                domain,
                source,
                pending_id,
                approved_abbreviation_id,
                is_active,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (
                NEWID(),
                TRY_CONVERT(UNIQUEIDENTIFIER, :user_id),
                :abbr,
                :expanded,
                :alternative_expansions_json,
                :domain,
                :source,
                TRY_CONVERT(UNIQUEIDENTIFIER, :pending_id),
                TRY_CONVERT(UNIQUEIDENTIFIER, :approved_abbreviation_id),
                1,
                SYSUTCDATETIME(),
                SYSUTCDATETIME(),
                :updated_by,
                :updated_by
            )
            """)
        update_stmt = text("""
            UPDATE dbo.user_abbreviation_overrides
            SET expanded = :expanded,
                alternative_expansions_json = :alternative_expansions_json,
                source = :source,
                pending_id = COALESCE(TRY_CONVERT(UNIQUEIDENTIFIER, :pending_id), pending_id),
                approved_abbreviation_id = COALESCE(
                    TRY_CONVERT(UNIQUEIDENTIFIER, :approved_abbreviation_id),
                    approved_abbreviation_id
                ),
                updated_at = SYSUTCDATETIME(),
                updated_by = :updated_by
            WHERE id = TRY_CONVERT(UNIQUEIDENTIFIER, :override_id)
            """)

        try:
            with self.session_factory() as session:
                existing = (
                    session.execute(
                        select_existing,
                        {"user_id": user_id, "abbr": abbr, "domain": domain},
                    )
                    .mappings()
                    .first()
                )
                existing_alternatives = []
                if existing:
                    existing_alternatives = self._merge_meaning_candidates(
                        self._deserialize_meanings(existing["alternative_expansions_json"]),
                        [str(existing["expanded"] or "")],
                    )
                alternative_expansions = self._merge_additional_meanings(
                    primary=meaning,
                    existing=existing_alternatives,
                    candidates=[],
                )
                params = {
                    "user_id": user_id,
                    "abbr": abbr,
                    "expanded": meaning,
                    "alternative_expansions_json": self._serialize_meanings(alternative_expansions),
                    "domain": domain,
                    "source": source,
                    "pending_id": pending_id,
                    "approved_abbreviation_id": approved_abbreviation_id,
                    "updated_by": updated_by or "system",
                }
                if existing:
                    session.execute(update_stmt, {**params, "override_id": existing["id"]})
                else:
                    session.execute(insert_stmt, params)
                saved = (
                    session.execute(
                        select_saved,
                        {"user_id": user_id, "abbr": abbr, "domain": domain},
                    )
                    .mappings()
                    .first()
                )
                session.commit()
                return self._normalize_user_override_record(dict(saved)) if saved else {}
        except Exception as exc:
            if self._is_missing_table_error(exc, self._USER_OVERRIDE_TABLE):
                self._set_table_exists(self._USER_OVERRIDE_TABLE, False)
                return {"abbr": abbr, "expanded": meaning, "status": "DB_SCHEMA_MISSING"}
            raise

    def list_pending_abbreviations(self, status: str = "PENDING") -> List[dict]:
        if not self.is_ready():
            return []

        query = text("""
            SELECT
                CAST(id AS NVARCHAR(36)) AS id,
                abbr,
                suggested,
                suggested_meanings_json,
                domain,
                source,
                status,
                submission_count,
                submitted_by,
                reviewed_by,
                review_notes,
                CAST(approved_abbreviation_id AS NVARCHAR(36)) AS approved_abbreviation_id,
                CONVERT(NVARCHAR(33), created_at, 126) AS created_at,
                CONVERT(NVARCHAR(33), updated_at, 126) AS updated_at
            FROM dbo.abbreviation_pending
            WHERE is_active = 1 AND status = :status
            ORDER BY created_at DESC
            """)
        with self.session_factory() as session:
            return [
                self._normalize_pending_record(dict(row))
                for row in session.execute(query, {"status": status}).mappings().all()
            ]

    def get_pending_abbreviation_detail(self, pending_id: str) -> Optional[dict]:
        if not self.is_ready():
            return None

        query = text("""
            SELECT
                CAST(id AS NVARCHAR(36)) AS id,
                abbr,
                suggested,
                suggested_meanings_json,
                domain,
                source,
                status,
                submission_count,
                submitted_by,
                reviewed_by,
                review_notes,
                CAST(approved_abbreviation_id AS NVARCHAR(36)) AS approved_abbreviation_id,
                CONVERT(NVARCHAR(33), created_at, 126) AS created_at,
                CONVERT(NVARCHAR(33), updated_at, 126) AS updated_at
            FROM dbo.abbreviation_pending
            WHERE is_active = 1 AND id = :pending_id
            """)
        with self.session_factory() as session:
            record = session.execute(query, {"pending_id": pending_id}).mappings().first()
            return self._normalize_pending_record(dict(record)) if record else None

    def submit_pending_abbreviation(
        self,
        abbr: str,
        suggested: Optional[str] = None,
        submitted_by: Optional[str] = None,
        source: str = "runtime",
        domain: str = "general",
    ) -> dict:
        if not self.is_ready():
            return {
                "abbr": abbr,
                "status": "DB_UNAVAILABLE",
                "pending_id": None,
                "has_suggested": False,
            }

        select_existing = text("""
            SELECT
                CAST(id AS NVARCHAR(36)) AS id,
                suggested,
                suggested_meanings_json
            FROM dbo.abbreviation_pending
            WHERE abbr = :abbr AND domain = :domain AND status = 'PENDING' AND is_active = 1
            """)
        update_existing = text("""
            UPDATE dbo.abbreviation_pending
            SET submission_count = submission_count + 1,
                last_submitted_at = SYSUTCDATETIME(),
                updated_at = SYSUTCDATETIME(),
                updated_by = :submitted_by
            WHERE id = :pending_id
            """)
        insert_new = text("""
            INSERT INTO dbo.abbreviation_pending (
                id,
                abbr,
                suggested,
                suggested_meanings_json,
                domain,
                source,
                status,
                submission_count,
                first_submitted_at,
                last_submitted_at,
                submitted_by,
                is_active,
                created_at,
                updated_at,
                created_by,
                updated_by
            )
            VALUES (
                NEWID(),
                :abbr,
                :suggested,
                :suggested_meanings_json,
                :domain,
                :source,
                'PENDING',
                1,
                SYSUTCDATETIME(),
                SYSUTCDATETIME(),
                :submitted_by,
                1,
                SYSUTCDATETIME(),
                SYSUTCDATETIME(),
                :submitted_by,
                :submitted_by
            )
            """)
        audit_insert = text("""
            INSERT INTO dbo.abbreviation_audit_log (
                id,
                pending_id,
                action,
                action_notes,
                actor_name,
                payload_json,
                created_at
            )
            VALUES (NEWID(), :pending_id, :action, :notes, :actor_name, :payload_json, SYSUTCDATETIME())
            """)

        with self.session_factory() as session:
            existing = (
                session.execute(select_existing, {"abbr": abbr, "domain": domain})
                .mappings()
                .first()
            )
            if existing:
                session.execute(
                    update_existing,
                    {"pending_id": existing["id"], "submitted_by": submitted_by or "system"},
                )
                session.execute(
                    audit_insert,
                    {
                        "pending_id": existing["id"],
                        "action": "RESUBMIT",
                        "notes": "Tang so lan de xuat",
                        "actor_name": submitted_by or "system",
                        "payload_json": '{"event":"resubmit"}',
                    },
                )
                session.commit()
                return {
                    "abbr": abbr,
                    "status": "PENDING_EXISTS",
                    "pending_id": existing["id"],
                    "has_suggested": self._has_text(existing["suggested"]),
                    "suggested_meanings": self._get_pending_meanings(existing),
                }

            suggested_meanings = self._merge_meaning_candidates([], [suggested or ""])
            session.execute(
                insert_new,
                {
                    "abbr": abbr,
                    "suggested": suggested,
                    "suggested_meanings_json": self._serialize_meanings(suggested_meanings),
                    "domain": domain,
                    "source": source,
                    "submitted_by": submitted_by or "system",
                },
            )
            # Read the id back with an explicit filter on the OPEN row. The old
            # "newest row for this abbr" query could return an unrelated older
            # pending (or a concurrently inserted duplicate) whenever two
            # keystroke-driven requests raced, so the meaning the user typed was
            # then attached to the wrong row.
            pending_id = session.execute(
                text("""
                    SELECT TOP 1 CAST(id AS NVARCHAR(36)) AS id
                    FROM dbo.abbreviation_pending
                    WHERE abbr = :abbr
                      AND domain = :domain
                      AND status = N'PENDING'
                      AND is_active = 1
                    ORDER BY created_at DESC, id DESC
                    """),
                {"abbr": abbr, "domain": domain},
            ).scalar_one()
            session.execute(
                audit_insert,
                {
                    "pending_id": pending_id,
                    "action": "SUBMIT",
                    "notes": "Tao pending moi",
                    "actor_name": submitted_by or "system",
                    "payload_json": '{"event":"submit"}',
                },
            )
            session.commit()
            return {
                "abbr": abbr,
                "status": "PENDING_CREATED",
                "pending_id": pending_id,
                "has_suggested": self._has_text(suggested),
                "suggested_meanings": suggested_meanings,
            }

    def capture_pending_suggestion(
        self,
        pending_id: str,
        suggested: str,
        submitted_by: Optional[str] = None,
    ) -> dict:
        if not self.is_ready():
            return {"pending_id": pending_id, "status": "DB_UNAVAILABLE"}

        cleaned = suggested.strip()
        if not cleaned:
            return {"pending_id": pending_id, "status": "IGNORED"}

        select_pending = text("""
            SELECT
                CAST(id AS NVARCHAR(36)) AS id,
                suggested,
                suggested_meanings_json
            FROM dbo.abbreviation_pending
            WHERE id = :pending_id AND status = 'PENDING' AND is_active = 1
            """)
        update_pending = text("""
            UPDATE dbo.abbreviation_pending
            SET suggested = :suggested,
                suggested_meanings_json = :suggested_meanings_json,
                updated_at = SYSUTCDATETIME(),
                updated_by = :submitted_by
            WHERE id = :pending_id
            """)
        audit_insert = text("""
            INSERT INTO dbo.abbreviation_audit_log (
                id,
                pending_id,
                action,
                action_notes,
                actor_name,
                payload_json,
                created_at
            )
            VALUES (NEWID(), :pending_id, 'CAPTURE_SUGGESTION', :notes, :actor_name, :payload_json, SYSUTCDATETIME())
            """)

        with self.session_factory() as session:
            pending = session.execute(select_pending, {"pending_id": pending_id}).mappings().first()
            if not pending:
                return {"pending_id": pending_id, "status": "PENDING_NOT_FOUND"}
            current_suggested = str(pending["suggested"] or "").strip()
            existing_meanings = self._get_pending_meanings(pending)
            if cleaned in existing_meanings:
                return {
                    "pending_id": pending_id,
                    "status": "SUGGESTION_ALREADY_EXISTS",
                    "has_suggested": True,
                    "suggested_meanings": existing_meanings,
                }

            updated_meanings = self._merge_meaning_candidates(existing_meanings, [cleaned])
            primary_suggested = current_suggested or cleaned
            status = "SUGGESTION_CAPTURED" if not current_suggested else "SUGGESTION_APPENDED"

            session.execute(
                update_pending,
                {
                    "pending_id": pending_id,
                    "suggested": primary_suggested,
                    "suggested_meanings_json": self._serialize_meanings(updated_meanings),
                    "submitted_by": submitted_by or "system",
                },
            )
            session.execute(
                audit_insert,
                {
                    "pending_id": pending_id,
                    "notes": "CLI cap nhat nghia goc cho pending",
                    "actor_name": submitted_by or "system",
                    "payload_json": json.dumps(
                        {"event": "capture_suggestion", "suggested": cleaned, "status": status},
                        ensure_ascii=False,
                    ),
                },
            )
            session.commit()
            return {
                "pending_id": pending_id,
                "status": status,
                "has_suggested": True,
                "suggested_meanings": updated_meanings,
            }

    def approve_pending_abbreviation(
        self,
        pending_id: str,
        reviewer: str,
        expanded: Optional[str] = None,
        review_notes: Optional[str] = None,
    ) -> dict:
        if not self.is_ready():
            raise RuntimeError("SQL Server chua san sang.")

        select_pending = text("""
            SELECT
                CAST(id AS NVARCHAR(36)) AS id,
                abbr,
                suggested,
                suggested_meanings_json,
                domain,
                source,
                status
            FROM dbo.abbreviation_pending
            WHERE id = :pending_id AND is_active = 1
            """)
        select_existing = text("""
            SELECT
                CAST(id AS NVARCHAR(36)) AS id,
                expanded,
                alternative_expansions_json
            FROM dbo.abbreviations
            WHERE abbr = :abbr AND domain = :domain AND is_active = 1
            """)
        insert_abbr = text("""
            INSERT INTO dbo.abbreviations (
                id,
                abbr,
                expanded,
                alternative_expansions_json,
                domain,
                source,
                approved,
                is_active,
                created_at,
                updated_at,
                approved_at,
                approved_by
            )
            VALUES (
                NEWID(),
                :abbr,
                :expanded,
                :alternative_expansions_json,
                :domain,
                :source,
                1,
                1,
                SYSUTCDATETIME(),
                SYSUTCDATETIME(),
                SYSUTCDATETIME(),
                :reviewer
            )
            """)
        update_abbr = text("""
            UPDATE dbo.abbreviations
            SET alternative_expansions_json = :alternative_expansions_json,
                source = :source,
                approved = 1,
                updated_at = SYSUTCDATETIME(),
                approved_at = SYSUTCDATETIME(),
                approved_by = :reviewer
            WHERE id = :abbreviation_id
            """)
        update_pending = text("""
            UPDATE dbo.abbreviation_pending
            SET status = 'APPROVED',
                approved_abbreviation_id = :abbreviation_id,
                reviewed_by = :reviewer,
                review_notes = :review_notes,
                updated_at = SYSUTCDATETIME(),
                updated_by = :reviewer
            WHERE id = :pending_id
            """)
        audit_insert = text("""
            INSERT INTO dbo.abbreviation_audit_log (
                id,
                pending_id,
                abbreviation_id,
                action,
                action_notes,
                actor_name,
                payload_json,
                created_at
            )
            VALUES (NEWID(), :pending_id, :abbreviation_id, 'APPROVE', :notes, :actor_name, '{"event":"approve"}', SYSUTCDATETIME())
            """)

        with self.session_factory() as session:
            pending = session.execute(select_pending, {"pending_id": pending_id}).mappings().first()
            if not pending:
                raise ValueError("Khong tim thay pending record.")
            if pending["status"] != "PENDING":
                raise ValueError("Pending record khong o trang thai PENDING.")

            final_expanded = (expanded or pending["suggested"] or "").strip()
            if not final_expanded:
                raise ValueError("Can cung cap nghia sau khi duyet.")

            pending_meanings = self._get_pending_meanings(pending)
            pending_meanings = self._merge_meaning_candidates(pending_meanings, [final_expanded])
            existing = (
                session.execute(
                    select_existing,
                    {"abbr": pending["abbr"], "domain": pending["domain"]},
                )
                .mappings()
                .first()
            )
            if existing:
                abbreviation_id = existing["id"]
                primary_expanded = str(existing["expanded"] or "").strip()
                alternative_expansions = self._merge_additional_meanings(
                    primary=primary_expanded,
                    existing=self._deserialize_meanings(existing["alternative_expansions_json"]),
                    candidates=pending_meanings,
                )
                session.execute(
                    update_abbr,
                    {
                        "abbreviation_id": abbreviation_id,
                        "alternative_expansions_json": self._serialize_meanings(
                            alternative_expansions
                        ),
                        "source": pending["source"],
                        "reviewer": reviewer,
                    },
                )
            else:
                alternative_expansions = self._merge_additional_meanings(
                    primary=final_expanded,
                    existing=[],
                    candidates=pending_meanings,
                )
                session.execute(
                    insert_abbr,
                    {
                        "abbr": pending["abbr"],
                        "expanded": final_expanded,
                        "alternative_expansions_json": self._serialize_meanings(
                            alternative_expansions
                        ),
                        "domain": pending["domain"],
                        "source": pending["source"],
                        "reviewer": reviewer,
                    },
                )
                created_abbreviation = (
                    session.execute(
                        select_existing,
                        {"abbr": pending["abbr"], "domain": pending["domain"]},
                    )
                    .mappings()
                    .first()
                )
                abbreviation_id = created_abbreviation["id"]

            session.execute(
                update_pending,
                {
                    "pending_id": pending_id,
                    "abbreviation_id": abbreviation_id,
                    "reviewer": reviewer,
                    "review_notes": review_notes,
                },
            )
            session.execute(
                audit_insert,
                {
                    "pending_id": pending_id,
                    "abbreviation_id": abbreviation_id,
                    "notes": review_notes or "Duyet pending vao bang chinh",
                    "actor_name": reviewer,
                },
            )
            session.commit()
            return {
                "pending_id": pending_id,
                "abbreviation_id": abbreviation_id,
                "status": "APPROVED",
            }

    def reject_pending_abbreviation(
        self, pending_id: str, reviewer: str, review_notes: Optional[str] = None
    ) -> dict:
        if not self.is_ready():
            raise RuntimeError("SQL Server chua san sang.")

        update_pending = text("""
            UPDATE dbo.abbreviation_pending
            SET status = 'REJECTED',
                reviewed_by = :reviewer,
                review_notes = :review_notes,
                updated_at = SYSUTCDATETIME(),
                updated_by = :reviewer
            WHERE id = :pending_id AND is_active = 1
            """)
        audit_insert = text("""
            INSERT INTO dbo.abbreviation_audit_log (
                id,
                pending_id,
                action,
                action_notes,
                actor_name,
                payload_json,
                created_at
            )
            VALUES (NEWID(), :pending_id, 'REJECT', :notes, :actor_name, '{"event":"reject"}', SYSUTCDATETIME())
            """)

        with self.session_factory() as session:
            result = session.execute(
                update_pending,
                {"pending_id": pending_id, "reviewer": reviewer, "review_notes": review_notes},
            )
            if result.rowcount == 0:
                raise ValueError("Khong tim thay pending record de reject.")
            session.execute(
                audit_insert,
                {
                    "pending_id": pending_id,
                    "notes": review_notes or "Tu choi pending",
                    "actor_name": reviewer,
                },
            )
            session.commit()
            return {"pending_id": pending_id, "status": "REJECTED"}

    def bulk_upsert_abbreviations(
        self,
        abbreviations: Iterable[dict],
        approved_by: str = "seed",
        replace_alternatives: bool = False,
    ) -> int:
        """Upsert approved abbreviations.

        ``replace_alternatives=False`` (the default, used by seeding) MERGES the
        incoming alternatives with whatever is already stored. Re-running the
        documented seed step used to overwrite ``alternative_expansions_json``
        with the seed file's value, permanently deleting every extra meaning an
        admin had approved.
        """
        if not self.is_ready():
            return 0

        count = 0
        select_existing = text("""
            SELECT
                CAST(id AS NVARCHAR(36)) AS id,
                alternative_expansions_json,
                approved_by
            FROM dbo.abbreviations
            WHERE abbr = :abbr AND domain = :domain AND is_active = 1
            """)
        insert_stmt = text("""
            INSERT INTO dbo.abbreviations (
                id, abbr, expanded, alternative_expansions_json, domain, source, approved, is_active, created_at, updated_at, approved_at, approved_by
            )
            VALUES (
                NEWID(), :abbr, :expanded, :alternative_expansions_json, :domain, :source, 1, 1, SYSUTCDATETIME(), SYSUTCDATETIME(), SYSUTCDATETIME(), :approved_by
            )
            """)
        update_stmt = text("""
            UPDATE dbo.abbreviations
            SET expanded = :expanded,
                alternative_expansions_json = :alternative_expansions_json,
                source = :source,
                approved = 1,
                updated_at = SYSUTCDATETIME(),
                approved_by = :approved_by
            WHERE id = :abbreviation_id
            """)

        with self.session_factory() as session:
            for record in abbreviations:
                domain = record.get("domain", "general")
                existing = (
                    session.execute(
                        select_existing,
                        {"abbr": record["abbr"], "domain": domain},
                    )
                    .mappings()
                    .first()
                )
                # Merge against what is already stored unless the caller is
                # explicitly authoritative (admin editing the dictionary).
                if (existing and not replace_alternatives
                        and existing.get("approved_by") not in (None, "", "seed")):
                    # Bootstrap must not restore meanings an admin replaced or removed.
                    continue
                stored_alternatives = (
                    []
                    if (replace_alternatives or not existing)
                    else self._deserialize_meanings(existing["alternative_expansions_json"])
                )
                alternative_expansions = self._merge_additional_meanings(
                    primary=record["expanded"],
                    existing=stored_alternatives,
                    candidates=self._deserialize_meanings(record.get("alternative_expansions")),
                )
                params = {
                    "abbr": record["abbr"],
                    "expanded": record["expanded"],
                    "alternative_expansions_json": self._serialize_meanings(alternative_expansions),
                    "domain": domain,
                    "source": record.get("source", "json_seed"),
                    "approved_by": approved_by,
                }
                if existing:
                    session.execute(update_stmt, {**params, "abbreviation_id": existing["id"]})
                else:
                    session.execute(insert_stmt, params)
                count += 1
            session.commit()
        return count

    def bulk_upsert_dictionary_words(
        self, dictionary_name: str, words: Iterable[str], approved_by: str = "seed"
    ) -> int:
        if not self.is_ready():
            return 0

        count = 0
        merge_stmt = text("""
            MERGE dbo.dictionary_entries AS target
            USING (SELECT :word AS word, :dictionary_name AS dictionary_name) AS source
            ON target.word = source.word AND target.dictionary_name = source.dictionary_name
            WHEN MATCHED THEN
                UPDATE SET
                    approved = 1,
                    is_active = 1,
                    updated_at = SYSUTCDATETIME(),
                    approved_by = :approved_by
            WHEN NOT MATCHED THEN
                INSERT (id, word, dictionary_name, source, approved, is_active, created_at, updated_at, approved_by)
                VALUES (NEWID(), :word, :dictionary_name, 'json_seed', 1, 1, SYSUTCDATETIME(), SYSUTCDATETIME(), :approved_by);
            """)

        with self.session_factory() as session:
            for word in words:
                session.execute(
                    merge_stmt,
                    {
                        "word": word,
                        "dictionary_name": dictionary_name,
                        "approved_by": approved_by,
                    },
                )
                count += 1
            session.commit()
        return count

    @staticmethod
    def _has_text(value: Optional[str]) -> bool:
        return bool(value and value.strip())

    @staticmethod
    def _deserialize_meanings(value: Optional[object]) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            raw_items = value
        elif isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            try:
                loaded = json.loads(stripped)
            except json.JSONDecodeError:
                raw_items = [stripped]
            else:
                raw_items = loaded if isinstance(loaded, list) else [loaded]
        else:
            raw_items = [value]

        normalized: List[str] = []
        for item in raw_items:
            cleaned = str(item or "").strip()
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)
        return normalized

    @classmethod
    def _merge_meaning_candidates(cls, existing: List[str], candidates: List[str]) -> List[str]:
        merged = list(existing)
        for candidate in candidates:
            cleaned = str(candidate or "").strip()
            if cleaned and cleaned not in merged:
                merged.append(cleaned)
        return merged

    @classmethod
    def _merge_additional_meanings(
        cls,
        primary: str,
        existing: List[str],
        candidates: List[str],
    ) -> List[str]:
        normalized_primary = primary.strip()
        merged = cls._merge_meaning_candidates(existing, candidates)
        return [meaning for meaning in merged if meaning != normalized_primary]

    @classmethod
    def _get_pending_meanings(cls, pending: dict) -> List[str]:
        existing_meanings = cls._deserialize_meanings(pending.get("suggested_meanings_json"))
        suggested = str(pending.get("suggested") or "").strip()
        if suggested:
            return cls._merge_meaning_candidates([suggested], existing_meanings)
        return existing_meanings

    @classmethod
    def _normalize_approved_record(cls, record: dict) -> dict:
        record["alternative_expansions"] = cls._deserialize_meanings(
            record.get("alternative_expansions_json")
        )
        record.pop("alternative_expansions_json", None)
        return record

    @classmethod
    def _normalize_pending_record(cls, record: dict) -> dict:
        record["suggested_meanings"] = cls._get_pending_meanings(record)
        record["has_suggested"] = bool(record["suggested_meanings"])
        record.pop("suggested_meanings_json", None)
        return record

    @classmethod
    def _normalize_user_override_record(cls, record: dict) -> dict:
        record["alternative_expansions"] = cls._deserialize_meanings(
            record.get("alternative_expansions_json")
        )
        record.pop("alternative_expansions_json", None)
        return record

    @classmethod
    def _serialize_meanings(cls, meanings: List[str]) -> Optional[str]:
        normalized = cls._deserialize_meanings(meanings)
        if not normalized:
            return None
        return json.dumps(normalized, ensure_ascii=False)

    # A negative answer expires so that applying init_schema.sql to a running
    # deployment takes effect without a restart. A positive answer is permanent
    # (a table does not disappear) and therefore costs no extra round-trip.
    _MISSING_TABLE_TTL_SECONDS = 60.0

    def _table_exists(self, table_name: str) -> bool:
        cache_key = (self.settings, table_name.lower())
        now = time.monotonic()
        with self._schema_table_cache_lock:
            cached = self._schema_table_cache.get(cache_key)
        if cached is not None:
            exists, expires_at = self._normalize_cache_entry(cached)
            if exists or expires_at > now:
                return exists

        query = text("SELECT CASE WHEN OBJECT_ID(:table_name, N'U') IS NULL THEN 0 ELSE 1 END")
        with self.session_factory() as session:
            exists = bool(session.execute(query, {"table_name": table_name}).scalar())
        self._set_table_exists(table_name, exists)
        return exists

    @staticmethod
    def _normalize_cache_entry(cached: object) -> tuple[bool, float]:
        """Accept both the bare-bool legacy shape and the (bool, expiry) shape."""
        if isinstance(cached, tuple):
            return bool(cached[0]), float(cached[1])
        return bool(cached), float("inf") if cached else 0.0

    def _set_table_exists(self, table_name: str, exists: bool) -> None:
        cache_key = (self.settings, table_name.lower())
        expires_at = (
            float("inf") if exists else time.monotonic() + self._MISSING_TABLE_TTL_SECONDS
        )
        with self._schema_table_cache_lock:
            self._schema_table_cache[cache_key] = (exists, expires_at)

    @classmethod
    def reset_schema_table_cache(cls) -> None:
        """Forget cached schema probes — call after applying a migration."""
        with cls._schema_table_cache_lock:
            cls._schema_table_cache.clear()

    @staticmethod
    def _is_missing_table_error(exc: Exception, table_name: str) -> bool:
        """Recognise "invalid object name" for *this* table.

        Prefers the driver SQLSTATE (42S02) when one is available and falls back
        to message matching, which is all that non-DBAPI errors expose.
        """
        normalized_table = table_name.lower()
        short_table = normalized_table.split(".")[-1]

        orig = getattr(exc, "orig", None)
        sqlstate = getattr(orig, "sqlstate", None)
        if sqlstate is None and orig is not None:
            args = getattr(orig, "args", ())
            if args and isinstance(args[0], str):
                sqlstate = args[0]
        if isinstance(sqlstate, str) and sqlstate.upper() == "42S02":
            message = str(exc).lower()
            return normalized_table in message or short_table in message

        message = str(exc).lower()
        references_table = normalized_table in message or short_table in message
        return references_table and ("invalid object name" in message or "42s02" in message)
