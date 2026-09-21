import datetime as dt
import hashlib
import unittest

from app.auth.security import (
    decode_access_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.auth.service import AuthService
from app.config import Settings


def _legacy_sha256_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-16le")).hexdigest().upper()


class FakeUserRepository:
    def __init__(self):
        self.users = {}
        self.created_payloads = []
        self.rehashed = []
        self.guard_state = {}
        self.failed_logins = []
        self.successful_logins = []

    def is_ready(self):
        return True

    def get_login_guard_state(self, user_id):
        return self.guard_state.get(
            user_id, {"failed_attempts": 0, "locked_until": None}
        )

    def register_failed_login(self, user_id, max_attempts, lockout_minutes):
        self.failed_logins.append((user_id, max_attempts, lockout_minutes))

    def register_successful_login(self, user_id):
        self.successful_logins.append(user_id)

    def _public_view(self, user):
        return {k: v for k, v in user.items() if k != "password_hash"}

    def find_by_identifier(self, identifier):
        for user in self.users.values():
            if user["username"] == identifier or user["email"] == identifier:
                return self._public_view(user)
        return None

    def find_for_authentication(self, identifier):
        for user in self.users.values():
            if user["username"] == identifier or user["email"] == identifier:
                return self._public_view(user), user.get("password_hash", "")
        return None

    def update_password_hash(self, user_id, new_hash):
        self.rehashed.append((user_id, new_hash))
        if user_id in self.users:
            self.users[user_id]["password_hash"] = new_hash

    def create_user(self, username, email, password_hash, role_name="user"):
        user = {
            "id": "user-1",
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "roles": [role_name],
            "is_active": True,
        }
        self.users[user["id"]] = user
        self.created_payloads.append(self._public_view(user))
        return self._public_view(user)


class FakeSessionRepository:
    def __init__(self):
        self.created_sessions = []
        self.revoked_tokens = []
        self.revoke_result = True

    def create_session(self, user_id, token, expires_at):
        session = {
            "user_id": user_id,
            "token": token,
            "expires_at": expires_at,
        }
        self.created_sessions.append(session)
        return session

    def revoke_token(self, token, reason=None):
        self.revoked_tokens.append((token, reason))
        return self.revoke_result


class AuthServiceTests(unittest.TestCase):
    def test_register_creates_user_and_returns_token(self):
        repository = FakeUserRepository()
        session_repository = FakeSessionRepository()
        service = AuthService(
            Settings(),
            user_repository=repository,
            session_repository=session_repository,
        )

        result = service.register("demo", "demo@example.com", "Secret@123")

        self.assertEqual(result["status"], "REGISTERED")
        stored_hash = repository.users["user-1"]["password_hash"]
        self.assertTrue(verify_password("Secret@123", stored_hash))
        self.assertFalse(needs_rehash(stored_hash))
        payload = decode_access_token(result["access_token"], Settings())
        self.assertEqual(payload["username"], "demo")
        self.assertEqual(payload["roles"], ["user"])
        self.assertEqual(
            session_repository.created_sessions,
            [
                {
                    "user_id": "user-1",
                    "token": result["access_token"],
                    "expires_at": result["expires_at"],
                }
            ],
        )

    def test_login_accepts_bcrypt_hash(self):
        repository = FakeUserRepository()
        repository.users["admin-1"] = {
            "id": "admin-1",
            "username": "admin_main",
            "email": "admin@vietnormalizer.local",
            "password_hash": hash_password("Admin@123"),
            "roles": ["admin"],
            "is_active": True,
        }
        session_repository = FakeSessionRepository()
        service = AuthService(
            Settings(),
            user_repository=repository,
            session_repository=session_repository,
        )

        result = service.login("admin_main", "Admin@123")

        self.assertEqual(result["status"], "AUTHENTICATED")
        payload = decode_access_token(result["access_token"], Settings())
        self.assertEqual(payload["email"], "admin@vietnormalizer.local")
        self.assertEqual(payload["roles"], ["admin"])
        self.assertEqual(session_repository.created_sessions[0]["user_id"], "admin-1")
        self.assertEqual(session_repository.created_sessions[0]["token"], result["access_token"])
        # Bcrypt hash should not trigger a rehash.
        self.assertEqual(repository.rehashed, [])

    def test_login_with_legacy_sha256_hash_triggers_rehash(self):
        repository = FakeUserRepository()
        repository.users["admin-1"] = {
            "id": "admin-1",
            "username": "admin_main",
            "email": "admin@vietnormalizer.local",
            "password_hash": _legacy_sha256_hash("Admin@123"),
            "roles": ["admin"],
            "is_active": True,
        }
        service = AuthService(
            Settings(),
            user_repository=repository,
            session_repository=FakeSessionRepository(),
        )

        result = service.login("admin_main", "Admin@123")

        self.assertEqual(result["status"], "AUTHENTICATED")
        self.assertEqual(len(repository.rehashed), 1)
        rehashed_user_id, new_hash = repository.rehashed[0]
        self.assertEqual(rehashed_user_id, "admin-1")
        self.assertFalse(needs_rehash(new_hash))
        self.assertTrue(verify_password("Admin@123", new_hash))

    def test_login_rejects_invalid_credentials(self):
        repository = FakeUserRepository()
        repository.users["user-1"] = {
            "id": "user-1",
            "username": "demo",
            "email": "demo@example.com",
            "password_hash": hash_password("Secret@123"),
            "roles": ["user"],
            "is_active": True,
        }
        session_repository = FakeSessionRepository()
        service = AuthService(
            Settings(),
            user_repository=repository,
            session_repository=session_repository,
        )

        result = service.login("demo", "wrong-password")

        self.assertEqual(result["status"], "INVALID_CREDENTIALS")
        self.assertEqual(session_repository.created_sessions, [])

    def test_logout_revokes_token(self):
        session_repository = FakeSessionRepository()
        service = AuthService(
            Settings(),
            user_repository=FakeUserRepository(),
            session_repository=session_repository,
        )

        result = service.logout("token-1")

        self.assertEqual(result, {"status": "LOGGED_OUT", "revoked": True})
        self.assertEqual(session_repository.revoked_tokens, [("token-1", "logout")])

    def test_logout_reports_when_nothing_was_revoked(self):
        session_repository = FakeSessionRepository()
        session_repository.revoke_result = False
        service = AuthService(
            Settings(),
            user_repository=FakeUserRepository(),
            session_repository=session_repository,
        )

        self.assertEqual(service.logout("token-1")["revoked"], False)

    def test_failed_login_is_counted_and_locked_account_is_rejected(self):
        user_repository = FakeUserRepository()
        user_repository.create_user("demo", "demo@example.com", hash_password("Secret@123"))
        service = AuthService(
            Settings(),
            user_repository=user_repository,
            session_repository=FakeSessionRepository(),
        )

        self.assertEqual(service.login("demo", "wrong")["status"], "INVALID_CREDENTIALS")
        self.assertEqual(len(user_repository.failed_logins), 1)

        # A locked account must answer exactly like a wrong password, otherwise
        # the response becomes an account-existence oracle.
        user_repository.guard_state["user-1"] = {
            "failed_attempts": 99,
            "locked_until": dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5),
        }
        result = service.login("demo", "Secret@123")
        self.assertEqual(result["status"], "INVALID_CREDENTIALS")
        self.assertNotIn("access_token", result)

    def test_successful_login_resets_the_failure_counter(self):
        user_repository = FakeUserRepository()
        user_repository.create_user("demo", "demo@example.com", hash_password("Secret@123"))
        service = AuthService(
            Settings(),
            user_repository=user_repository,
            session_repository=FakeSessionRepository(),
        )

        self.assertEqual(service.login("demo", "Secret@123")["status"], "AUTHENTICATED")
        self.assertEqual(user_repository.successful_logins, ["user-1"])

    def test_register_rejects_password_longer_than_bcrypt_can_read(self):
        service = AuthService(
            Settings(),
            user_repository=FakeUserRepository(),
            session_repository=FakeSessionRepository(),
        )

        result = service.register("demo", "demo@example.com", "a" * 73)

        self.assertEqual(result["status"], "PASSWORD_TOO_LONG")


if __name__ == "__main__":
    unittest.main()
