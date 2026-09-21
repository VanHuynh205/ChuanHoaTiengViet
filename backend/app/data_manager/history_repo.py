from __future__ import annotations

import datetime as dt
import json
from uuid import uuid4
from typing import Iterable, Optional

from app.data_manager.db import get_session_factory

try:
    from sqlalchemy import text
except ImportError:  # pragma: no cover - optional dependency in early setup
    text = None  # type: ignore[assignment]


class HistoryRepository:
    def __init__(self, settings) -> None:
        self.settings = settings
        self.session_factory = get_session_factory(settings)

    def is_ready(self) -> bool:
        return self.session_factory is not None and text is not None

    def log_normalization(
        self,
        input_text: str,
        output_text: Optional[str],
        error_types: Iterable[str],
        model_used: Optional[str] = None,
        from_cache: bool = False,
        latency_ms: Optional[float] = None,
        domain: str = "general",
        source_kind: str = "rule_based",
        username_snapshot: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[dict]:
        if not self.is_ready():
            return None

        history_id = str(uuid4())
        created_at = dt.datetime.now(dt.timezone.utc)
        normalized_error_types = list(error_types)

        insert_stmt = text("""
            INSERT INTO dbo.normalization_history (
                id,
                input_text,
                output_text,
                error_types_json,
                model_used,
                from_cache,
                latency_ms,
                domain,
                source_kind,
                user_id,
                username_snapshot,
                created_at
            )
            VALUES (
                :id,
                :input_text,
                :output_text,
                :error_types_json,
                :model_used,
                :from_cache,
                :latency_ms,
                :domain,
                :source_kind,
                :user_id,
                :username_snapshot,
                :created_at
            )
            """)

        with self.session_factory() as session:
            session.execute(
                insert_stmt,
                {
                    "id": history_id,
                    "input_text": input_text,
                    "output_text": output_text,
                    "error_types_json": json.dumps(normalized_error_types, ensure_ascii=False),
                    "model_used": model_used,
                    "from_cache": 1 if from_cache else 0,
                    "latency_ms": latency_ms,
                    "domain": domain,
                    "source_kind": source_kind,
                    "user_id": user_id,
                    "username_snapshot": username_snapshot,
                    "created_at": created_at,
                },
            )
            session.commit()
        return {
            "id": history_id,
            "input_text": input_text,
            "output_text": output_text,
            "error_types": normalized_error_types,
            "model_used": model_used,
            "from_cache": from_cache,
            "latency_ms": latency_ms,
            "domain": domain,
            "source_kind": source_kind,
            "user_id": user_id,
            "username_snapshot": username_snapshot,
            "created_at": created_at.isoformat(),
        }

    def list_history(self, user_id: str, limit: int = 30) -> list[dict]:
        if not self.is_ready():
            return []
        if not user_id:
            raise ValueError("HISTORY_OWNER_REQUIRED")

        normalized_limit = max(1, min(limit, 100))
        query = text("""
            SELECT
                CAST(id AS NVARCHAR(36)) AS id,
                input_text,
                output_text,
                error_types_json,
                model_used,
                CAST(from_cache AS INT) AS from_cache,
                latency_ms,
                domain,
                source_kind,
                CAST(user_id AS NVARCHAR(36)) AS user_id,
                username_snapshot,
                created_at
            FROM dbo.normalization_history
            WHERE user_id = TRY_CONVERT(UNIQUEIDENTIFIER, :user_id)
            ORDER BY created_at DESC
            OFFSET 0 ROWS FETCH NEXT :limit ROWS ONLY
            """)
        params = {"user_id": user_id, "limit": normalized_limit}

        with self.session_factory() as session:
            return [
                self._normalize_history_row(row)
                for row in session.execute(query, params).mappings().all()
            ]

    def delete_history_entry(self, history_id: str, user_id: str) -> dict:
        if not self.is_ready():
            raise RuntimeError("SQL Server chua san sang.")
        if not user_id:
            raise ValueError("HISTORY_OWNER_REQUIRED")

        select_stmt = text("""
            SELECT
                CAST(id AS NVARCHAR(36)) AS id,
                input_text,
                output_text,
                error_types_json,
                model_used,
                CAST(from_cache AS INT) AS from_cache,
                latency_ms,
                domain,
                source_kind,
                CAST(user_id AS NVARCHAR(36)) AS user_id,
                username_snapshot,
                created_at
            FROM dbo.normalization_history
            WHERE id = TRY_CONVERT(UNIQUEIDENTIFIER, :history_id)
              AND CAST(user_id AS NVARCHAR(36)) = :user_id
            """)
        delete_stmt = text("""
            DELETE FROM dbo.normalization_history
            WHERE id = TRY_CONVERT(UNIQUEIDENTIFIER, :history_id)
              AND CAST(user_id AS NVARCHAR(36)) = :user_id
            """)
        params = {"history_id": history_id, "user_id": user_id}

        with self.session_factory() as session:
            record = session.execute(select_stmt, params).mappings().first()
            if not record:
                raise ValueError("HISTORY_NOT_FOUND")

            session.execute(delete_stmt, params)
            session.commit()
            return self._normalize_history_row(dict(record))

    def log_error(
        self,
        module: str,
        error_message: str,
        stack_trace: Optional[str] = None,
        payload_json: Optional[str] = None,
    ) -> None:
        if not self.is_ready():
            return

        insert_stmt = text("""
            INSERT INTO dbo.system_error_logs (
                id,
                module,
                error_message,
                stack_trace,
                payload_json,
                created_at
            )
            VALUES (NEWID(), :module, :error_message, :stack_trace, :payload_json, SYSUTCDATETIME())
            """)

        with self.session_factory() as session:
            session.execute(
                insert_stmt,
                {
                    "module": module,
                    "error_message": error_message,
                    "stack_trace": stack_trace,
                    "payload_json": payload_json,
                },
            )
            session.commit()

    @staticmethod
    def _normalize_history_row(record: dict) -> dict:
        raw_error_types = record.get("error_types_json")
        error_types = []
        if raw_error_types:
            try:
                error_types = list(json.loads(raw_error_types))
            except (TypeError, json.JSONDecodeError):
                error_types = []

        created_at = record.get("created_at")
        return {
            "id": record["id"],
            "input_text": record["input_text"],
            "output_text": record.get("output_text"),
            "error_types": error_types,
            "model_used": record.get("model_used"),
            "from_cache": bool(record.get("from_cache", 0)),
            "latency_ms": record.get("latency_ms"),
            "domain": record.get("domain") or "general",
            "source_kind": record.get("source_kind") or "rule_based",
            "user_id": record.get("user_id"),
            "username_snapshot": record.get("username_snapshot"),
            "created_at": (
                created_at.isoformat()
                if hasattr(created_at, "isoformat")
                else str(created_at) if created_at else None
            ),
        }
