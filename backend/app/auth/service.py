from __future__ import annotations

import datetime as dt
import logging
from typing import Optional

from app.auth.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.config import Settings
from app.data_manager.new_tables_repo import SessionRepository
from app.data_manager.user_repo import UserRepository

logger = logging.getLogger(__name__)


def _is_locked(locked_until: object) -> bool:
    if not isinstance(locked_until, dt.datetime):
        return False
    # The column is stored as naive UTC (SYSUTCDATETIME).
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=dt.timezone.utc)
    return locked_until > dt.datetime.now(dt.timezone.utc)


class AuthService:
    def __init__(
        self,
        settings: Settings,
        user_repository: Optional[UserRepository] = None,
        session_repository: Optional[SessionRepository] = None,
    ) -> None:
        self.settings = settings
        self.user_repository = user_repository or UserRepository(settings)
        self.session_repository = session_repository or SessionRepository(settings)

    def is_ready(self) -> bool:
        return self.user_repository.is_ready()

    def register(self, username: str, email: str, password: str) -> dict:
        cleaned_username = username.strip()
        cleaned_email = email.strip().lower()
        # Do NOT strip the password — leading/trailing whitespace is part of
        # what the user typed and must round-trip exactly.
        if not cleaned_username or not cleaned_email or not password:
            return {"status": "INVALID_INPUT"}
        # bcrypt silently truncates at 72 bytes, so anything longer would only be
        # partially verified. Reject explicitly instead of pretending it counted.
        if len(password.encode("utf-8")) > 72:
            return {"status": "PASSWORD_TOO_LONG"}
        if not self.is_ready():
            return {"status": "DB_UNAVAILABLE"}
        if self.user_repository.find_by_identifier(
            cleaned_username
        ) or self.user_repository.find_by_identifier(cleaned_email):
            return {"status": "USER_EXISTS"}

        created_user = self.user_repository.create_user(
            username=cleaned_username,
            email=cleaned_email,
            password_hash=hash_password(password),
            role_name="user",
        )
        token = create_access_token(
            subject=created_user["id"],
            claims={
                "username": created_user["username"],
                "email": created_user["email"],
                "roles": created_user["roles"],
            },
            settings=self.settings,
        )
        self.session_repository.create_session(
            user_id=created_user["id"],
            token=token.token,
            expires_at=token.expires_at,
        )
        return {
            "status": "REGISTERED",
            "user": created_user,
            "access_token": token.token,
            "expires_at": token.expires_at,
        }

    def login(self, identifier: str, password: str) -> dict:
        cleaned_identifier = identifier.strip()
        if not cleaned_identifier or not password:
            return {"status": "INVALID_INPUT"}
        if not self.is_ready():
            return {"status": "DB_UNAVAILABLE"}

        credentials = self.user_repository.find_for_authentication(cleaned_identifier)
        if credentials is None:
            # Spend the same bcrypt time as a real check so response latency does
            # not reveal whether the account exists.
            verify_password(password, DUMMY_PASSWORD_HASH)
            return {"status": "INVALID_CREDENTIALS"}
        user, stored_hash = credentials
        if not user.get("is_active", True):
            return {"status": "INVALID_CREDENTIALS"}

        max_attempts = self.settings.auth_max_failed_logins
        lockout_enabled = max_attempts > 0
        if lockout_enabled:
            guard = self.user_repository.get_login_guard_state(user["id"])
            if _is_locked(guard.get("locked_until")):
                # Deliberately the same status as a wrong password: a distinct
                # "account locked" reply would be an enumeration oracle.
                logger.info("Rejected login for temporarily locked account %s", user["id"])
                return {"status": "INVALID_CREDENTIALS"}

        if not verify_password(password, stored_hash):
            if lockout_enabled:
                self.user_repository.register_failed_login(
                    user_id=user["id"],
                    max_attempts=max_attempts,
                    lockout_minutes=self.settings.auth_lockout_minutes,
                )
            return {"status": "INVALID_CREDENTIALS"}

        # Transparent rehash: migrate legacy SHA-256 hashes to bcrypt on next login.
        if needs_rehash(stored_hash):
            try:
                self.user_repository.update_password_hash(user["id"], hash_password(password))
            except Exception:  # pragma: no cover - non-fatal best-effort migration
                logger.warning(
                    "Failed to rehash legacy password for user %s", user["id"], exc_info=True
                )

        self.user_repository.register_successful_login(user["id"])

        token = create_access_token(
            subject=user["id"],
            claims={
                "username": user["username"],
                "email": user["email"],
                "roles": user["roles"],
            },
            settings=self.settings,
        )
        # Record session for server-side revocation support
        self.session_repository.create_session(
            user_id=user["id"],
            token=token.token,
            expires_at=token.expires_at,
        )

        return {
            "status": "AUTHENTICATED",
            "user": user,
            "access_token": token.token,
            "expires_at": token.expires_at,
        }

    def logout(self, token: str) -> dict:
        """Revoke a token server-side.

        Stays idempotent (clicking logout twice is not an error) but no longer
        swallows the difference between "already revoked" and "the session store
        never revoked anything".
        """
        revoked = self.session_repository.revoke_token(token, reason="logout")
        if not revoked:
            logger.warning("Logout did not revoke an active session row for this token.")
        return {"status": "LOGGED_OUT", "revoked": revoked}
