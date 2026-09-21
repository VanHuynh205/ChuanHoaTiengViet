from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from app.config import Settings
from app.data_manager.db import get_session_factory

try:
    from sqlalchemy import text
except ImportError:  # pragma: no cover - optional dependency in early setup
    text = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class UserRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session_factory = get_session_factory(settings)

    def is_ready(self) -> bool:
        return self.session_factory is not None and text is not None

    def find_by_identifier(self, identifier: str) -> Optional[dict]:
        if not self.is_ready():
            return None

        query = text("""
            SELECT
                CAST(u.id AS NVARCHAR(36)) AS id,
                u.username,
                u.email,
                CAST(u.is_active AS INT) AS is_active,
                u.created_at,
                u.updated_at,
                STUFF((
                    SELECT ',' + r.role_name
                    FROM dbo.user_roles ur
                    INNER JOIN dbo.roles r ON r.id = ur.role_id
                    WHERE ur.user_id = u.id
                    FOR XML PATH('')
                ), 1, 1, '') AS roles_csv
            FROM dbo.users u
            WHERE u.username = :identifier OR u.email = :identifier
            """)
        with self.session_factory() as session:
            record = session.execute(query, {"identifier": identifier}).mappings().first()
            return self._normalize_user(record) if record else None

    def find_for_authentication(self, identifier: str) -> Optional[Tuple[dict, str]]:
        """Return ``(user, password_hash)`` for auth flow only.

        The user dict is password-hash-free; the hash is returned separately so
        callers must be explicit about handling it. Never expose this method
        outside the authentication code path.
        """
        if not self.is_ready():
            return None

        query = text("""
            SELECT
                CAST(u.id AS NVARCHAR(36)) AS id,
                u.username,
                u.email,
                u.password_hash,
                CAST(u.is_active AS INT) AS is_active,
                u.created_at,
                u.updated_at,
                STUFF((
                    SELECT ',' + r.role_name
                    FROM dbo.user_roles ur
                    INNER JOIN dbo.roles r ON r.id = ur.role_id
                    WHERE ur.user_id = u.id
                    FOR XML PATH('')
                ), 1, 1, '') AS roles_csv
            FROM dbo.users u
            WHERE u.username = :identifier OR u.email = :identifier
            """)
        with self.session_factory() as session:
            record = session.execute(query, {"identifier": identifier}).mappings().first()
            if record is None:
                return None
            password_hash = str(record.get("password_hash") or "")
            return self._normalize_user(record), password_hash

    def update_password_hash(self, user_id: str, new_hash: str) -> None:
        """Update the stored password hash for ``user_id`` (transparent rehash)."""
        if not self.is_ready():
            raise RuntimeError("SQL Server chua san sang.")
        if not new_hash:
            raise ValueError("new_hash must be non-empty.")

        update = text("""
            UPDATE dbo.users
            SET password_hash = :password_hash, updated_at = SYSUTCDATETIME()
            WHERE id = TRY_CONVERT(UNIQUEIDENTIFIER, :user_id)
            """)
        with self.session_factory() as session:
            session.execute(update, {"password_hash": new_hash, "user_id": user_id})
            session.commit()

    def find_by_id(self, user_id: str) -> Optional[dict]:
        if not self.is_ready():
            return None

        query = text("""
            SELECT
                CAST(u.id AS NVARCHAR(36)) AS id,
                u.username,
                u.email,
                CAST(u.is_active AS INT) AS is_active,
                u.created_at,
                u.updated_at,
                STUFF((
                    SELECT ',' + r.role_name
                    FROM dbo.user_roles ur
                    INNER JOIN dbo.roles r ON r.id = ur.role_id
                    WHERE ur.user_id = u.id
                    FOR XML PATH('')
                ), 1, 1, '') AS roles_csv
            FROM dbo.users u
            WHERE u.id = TRY_CONVERT(UNIQUEIDENTIFIER, :user_id)
            """)
        with self.session_factory() as session:
            record = session.execute(query, {"user_id": user_id}).mappings().first()
            return self._normalize_user(record) if record else None

    def create_user(
        self, username: str, email: str, password_hash: str, role_name: str = "user"
    ) -> dict:
        if not self.is_ready():
            raise RuntimeError("SQL Server chua san sang.")

        insert_user = text("""
            INSERT INTO dbo.users (id, username, email, password_hash, is_active, created_at, updated_at)
            VALUES (NEWID(), :username, :email, :password_hash, 1, SYSUTCDATETIME(), SYSUTCDATETIME())
            """)
        assign_role = text("""
            INSERT INTO dbo.user_roles (user_id, role_id, assigned_at, assigned_by)
            SELECT u.id, r.id, SYSUTCDATETIME(), :assigned_by
            FROM dbo.users u
            CROSS JOIN dbo.roles r
            WHERE u.username = :username AND r.role_name = :role_name
            """)
        with self.session_factory() as session:
            session.execute(
                insert_user,
                {
                    "username": username,
                    "email": email,
                    "password_hash": password_hash,
                },
            )
            session.execute(
                assign_role,
                {
                    "username": username,
                    "role_name": role_name,
                    "assigned_by": "self_register",
                },
            )
            session.commit()
        created = self.find_by_identifier(username)
        if not created:
            raise RuntimeError("Khong tao duoc user.")
        return created

    def list_users(self) -> List[dict]:
        if not self.is_ready():
            return []

        query = text("""
            SELECT
                CAST(u.id AS NVARCHAR(36)) AS id,
                u.username,
                u.email,
                CAST(u.is_active AS INT) AS is_active,
                u.created_at,
                u.updated_at,
                STUFF((
                    SELECT ',' + r.role_name
                    FROM dbo.user_roles ur
                    INNER JOIN dbo.roles r ON r.id = ur.role_id
                    WHERE ur.user_id = u.id
                    FOR XML PATH('')
                ), 1, 1, '') AS roles_csv
            FROM dbo.users u
            ORDER BY u.created_at DESC
            """)
        with self.session_factory() as session:
            return [self._normalize_user(row) for row in session.execute(query).mappings().all()]

    def assign_role(self, user_id: str, role_name: str, assigned_by: str) -> dict:
        if not self.is_ready():
            raise RuntimeError("SQL Server chua san sang.")

        delete_roles = text("DELETE FROM dbo.user_roles WHERE user_id = :user_id")
        assign_role = text("""
            INSERT INTO dbo.user_roles (user_id, role_id, assigned_at, assigned_by)
            SELECT :user_id, r.id, SYSUTCDATETIME(), :assigned_by
            FROM dbo.roles r
            WHERE r.role_name = :role_name
            """)
        with self.session_factory() as session:
            session.execute(delete_roles, {"user_id": user_id})
            session.execute(
                assign_role,
                {
                    "user_id": user_id,
                    "role_name": role_name,
                    "assigned_by": assigned_by,
                },
            )
            session.commit()

        for user in self.list_users():
            if user["id"] == user_id:
                return user
        raise ValueError("Khong tim thay user sau khi cap nhat role.")

    def delete_user(self, user_id: str) -> dict:
        if not self.is_ready():
            raise RuntimeError("SQL Server chua san sang.")

        user = self.find_by_id(user_id)
        if not user:
            raise ValueError("USER_NOT_FOUND")
        if "admin" in user.get("roles", []):
            raise ValueError("ADMIN_USER_DELETE_FORBIDDEN")

        clear_history_refs = text(
            "UPDATE dbo.normalization_history SET user_id = NULL WHERE user_id = TRY_CONVERT(UNIQUEIDENTIFIER, :user_id)"
        )
        clear_error_log_refs = text(
            "UPDATE dbo.system_error_logs SET user_id = NULL WHERE user_id = TRY_CONVERT(UNIQUEIDENTIFIER, :user_id)"
        )
        delete_user_overrides = text(
            "DELETE FROM dbo.user_abbreviation_overrides WHERE user_id = TRY_CONVERT(UNIQUEIDENTIFIER, :user_id)"
        )
        # Schema v2 added two more tables with an FK to dbo.users. Without these
        # deletes the final DELETE violates the constraint, so removing any user
        # who had ever logged in (i.e. had a session row) failed with a 500.
        delete_sessions = text(
            "DELETE FROM dbo.user_sessions WHERE user_id = TRY_CONVERT(UNIQUEIDENTIFIER, :user_id)"
        )
        delete_preferences = text(
            "DELETE FROM dbo.user_preferences WHERE user_id = TRY_CONVERT(UNIQUEIDENTIFIER, :user_id)"
        )
        delete_roles = text(
            "DELETE FROM dbo.user_roles WHERE user_id = TRY_CONVERT(UNIQUEIDENTIFIER, :user_id)"
        )
        delete_user = text("DELETE FROM dbo.users WHERE id = TRY_CONVERT(UNIQUEIDENTIFIER, :user_id)")

        with self.session_factory() as session:
            session.execute(clear_history_refs, {"user_id": user_id})
            session.execute(clear_error_log_refs, {"user_id": user_id})
            session.execute(delete_user_overrides, {"user_id": user_id})
            session.execute(delete_sessions, {"user_id": user_id})
            session.execute(delete_preferences, {"user_id": user_id})
            session.execute(delete_roles, {"user_id": user_id})
            session.execute(delete_user, {"user_id": user_id})
            session.commit()

        return user

    # ------------------------------------------------------------------
    # Failed-login tracking (columns added in schema v2)
    # ------------------------------------------------------------------

    def get_login_guard_state(self, user_id: str) -> dict:
        """Return ``{failed_attempts, locked_until}`` for the lockout check.

        Missing columns (schema v1) degrade to "no lockout" rather than blocking
        logins, so this never becomes a self-inflicted outage.
        """
        if not self.is_ready():
            return {"failed_attempts": 0, "locked_until": None}

        query = text("""
            SELECT
                COALESCE(failed_login_attempts, 0) AS failed_login_attempts,
                locked_until
            FROM dbo.users
            WHERE id = TRY_CONVERT(UNIQUEIDENTIFIER, :user_id)
            """)
        try:
            with self.session_factory() as session:
                record = session.execute(query, {"user_id": user_id}).mappings().first()
        except Exception:
            logger.warning("Login guard state query failed; treating as unlocked.", exc_info=True)
            return {"failed_attempts": 0, "locked_until": None}
        if not record:
            return {"failed_attempts": 0, "locked_until": None}
        return {
            "failed_attempts": int(record.get("failed_login_attempts") or 0),
            "locked_until": record.get("locked_until"),
        }

    def register_failed_login(self, user_id: str, max_attempts: int, lockout_minutes: int) -> None:
        """Increment the failure counter and lock the account once over budget."""
        if not self.is_ready() or max_attempts <= 0:
            return

        update = text("""
            UPDATE dbo.users
            SET failed_login_attempts = COALESCE(failed_login_attempts, 0) + 1,
                locked_until = CASE
                    WHEN COALESCE(failed_login_attempts, 0) + 1 >= :max_attempts
                        THEN DATEADD(MINUTE, :lockout_minutes, SYSUTCDATETIME())
                    ELSE locked_until
                END,
                updated_at = SYSUTCDATETIME()
            WHERE id = TRY_CONVERT(UNIQUEIDENTIFIER, :user_id)
            """)
        try:
            with self.session_factory() as session:
                session.execute(
                    update,
                    {
                        "user_id": user_id,
                        "max_attempts": max_attempts,
                        "lockout_minutes": max(1, lockout_minutes),
                    },
                )
                session.commit()
        except Exception:
            # Schema v1 has no such columns; never break login over telemetry.
            logger.warning("Failed-login counter update failed; lockout not recorded.", exc_info=True)
            return

    def register_successful_login(self, user_id: str) -> None:
        """Reset the failure counter and stamp ``last_login_at``."""
        if not self.is_ready():
            return

        update = text("""
            UPDATE dbo.users
            SET failed_login_attempts = 0,
                locked_until = NULL,
                last_login_at = SYSUTCDATETIME()
            WHERE id = TRY_CONVERT(UNIQUEIDENTIFIER, :user_id)
            """)
        try:
            with self.session_factory() as session:
                session.execute(update, {"user_id": user_id})
                session.commit()
        except Exception:
            logger.warning("Successful-login counter reset failed.", exc_info=True)
            return

    @staticmethod
    def _normalize_user(record: dict) -> dict:
        roles_csv = str(record.get("roles_csv") or "")
        roles = [role for role in roles_csv.split(",") if role]
        normalized = {
            "id": record["id"],
            "username": record["username"],
            "email": record["email"],
            "roles": roles,
            "is_active": bool(record.get("is_active", True)),
        }
        created_at = record.get("created_at")
        updated_at = record.get("updated_at")
        if created_at is not None:
            normalized["created_at"] = (
                created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
            )
        if updated_at is not None:
            normalized["updated_at"] = (
                updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at)
            )
        return normalized
