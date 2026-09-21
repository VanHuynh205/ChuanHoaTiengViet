import unittest

from fastapi.testclient import TestClient

from app.api.dependencies import _get_session_repository, get_app_settings, get_current_user
from app.api.routes import (
    _get_auth_service,
    _get_history_repository,
    _get_pending_service,
    _get_user_repository,
    _should_apply_semantic_verification,
)
from app.api.server import _cors_origins, create_app
from app.auth.security import create_access_token
from app.auth.service import AuthService
from app.config import Settings
from app.data_manager.pending_service import LiveNormalizationData


class _SemanticProbe:
    def __init__(self, diacritic_applied=False, ambiguities=None, diacritic_changes=None):
        self.diacritic_applied = diacritic_applied
        self.ambiguities = ambiguities or []
        self.diacritic_changes = diacritic_changes or []


def test_dev_cors_accepts_vite_fallback_port_without_widening_production():
    settings = Settings(web_origin="http://localhost:5173", app_env="development")
    origins = _cors_origins(settings)
    assert "http://localhost:5174" in origins
    production = _cors_origins(Settings(web_origin="http://localhost:5173", app_env="production"))
    assert production == ["http://localhost:5173"]


class FakeAuthService(AuthService):
    def __init__(self, settings):
        self.settings = settings
        self.register_calls = []
        self.login_calls = []

    def register(self, username, email, password):
        self.register_calls.append((username, email, password))
        token = create_access_token(
            subject="user-1",
            claims={"username": username, "email": email, "roles": ["user"]},
            settings=self.settings,
        )
        return {
            "status": "REGISTERED",
            "user": {
                "id": "user-1",
                "username": username,
                "email": email,
                "roles": ["user"],
                "is_active": True,
            },
            "access_token": token.token,
            "expires_at": token.expires_at,
        }

    def login(self, identifier, password):
        self.login_calls.append((identifier, password))
        if identifier == "admin_main" and password == "Admin@123":
            token = create_access_token(
                subject="admin-1",
                claims={
                    "username": "admin_main",
                    "email": "admin@vietnormalizer.local",
                    "roles": ["admin"],
                },
                settings=self.settings,
            )
            return {
                "status": "AUTHENTICATED",
                "user": {
                    "id": "admin-1",
                    "username": "admin_main",
                    "email": "admin@vietnormalizer.local",
                    "roles": ["admin"],
                    "is_active": True,
                },
                "access_token": token.token,
                "expires_at": token.expires_at,
            }
        return {"status": "INVALID_CREDENTIALS"}


class FakePendingService:
    def __init__(self):
        self.ready = True
        self.saved_abbreviations = {
            "dk": {
                "id": "abbr-dk",
                "abbr": "dk",
                "expanded": "dang ky",
                "alternative_expansions": ["dung khong"],
                "domain": "general",
                "source": "sql_server",
                "created_at": None,
                "approved_by": "admin",
            }
        }
        self.user_meaning_calls = []
        self.admin_meaning_calls = []

    def db_is_ready(self):
        return self.ready

    def list_approved_abbreviations(self, abbr=None, domain=None):
        records = [
            record
            for record in self.saved_abbreviations.values()
            if domain is None or record["domain"] == domain
        ]
        if abbr:
            return [record for record in records if record["abbr"] == abbr]
        return records

    def get_approved_abbreviation_details(self, abbr, domain="general"):
        matches = self.list_approved_abbreviations(abbr=abbr, domain=domain)
        return matches[0] if matches else None

    def list_pending_abbreviations(self, status="PENDING"):
        return [
            {
                "id": "pending-dk",
                "abbr": "dk",
                "suggested": "dieu kien",
                "suggested_meanings": ["dieu kien"],
                "domain": "general",
                "source": "runtime",
                "status": status,
                "submission_count": 1,
                "submitted_by": "demo",
                "reviewed_by": None,
                "review_notes": None,
                "approved_abbreviation_id": None,
                "created_at": None,
                "updated_at": None,
                "has_suggested": True,
            }
        ]

    def get_pending_abbreviation_detail(self, pending_id):
        return self.list_pending_abbreviations()[0]

    def approve_pending_abbreviation(self, pending_id, reviewer, expanded=None, review_notes=None):
        return {
            "pending_id": pending_id,
            "status": "APPROVED",
            "expanded": expanded,
            "reviewer": reviewer,
        }

    def reject_pending_abbreviation(self, pending_id, reviewer, review_notes=None):
        return {"pending_id": pending_id, "status": "REJECTED", "reviewer": reviewer}

    def add_abbreviation_meaning(self, **kwargs):
        self.admin_meaning_calls.append(kwargs)
        return {"status": "APPROVED", **kwargs}

    def add_user_abbreviation_meaning(self, **kwargs):
        self.user_meaning_calls.append(kwargs)
        return {
            "status": "USER_MEANING_APPLIED",
            "abbr": kwargs["abbr"],
            "meaning": kwargs["meaning"],
            "pending_id": "pending-user-meaning",
            "review_required": True,
            "user_override": {
                "id": "override-user-meaning",
                "abbr": kwargs["abbr"],
                "expanded": kwargs["meaning"],
            },
        }

    def save_approved_abbreviation(
        self, abbr, expanded, reviewer, alternative_expansions=None, domain="general"
    ):
        record = {
            "id": f"abbr-{abbr}",
            "abbr": abbr,
            "expanded": expanded,
            "alternative_expansions": list(alternative_expansions or []),
            "domain": domain,
            "source": "admin_dictionary",
            "created_at": None,
            "approved_by": reviewer,
        }
        self.saved_abbreviations[abbr] = record
        return record

    def get_approved_abbreviations(self):
        return {"dk": "dang ky", "pk": "phai khong"}

    def get_dictionary_words(self):
        return {"hom", "nay", "di", "the", "ngan", "hang", "phai", "khong"}

    def get_live_normalization_data(self, domain="general", user_id=None):
        records = self.list_approved_abbreviations(domain=domain)
        return LiveNormalizationData(
            abbreviations=self.get_approved_abbreviations(),
            dictionary_words=self.get_dictionary_words(),
            approved_details={record["abbr"].lower(): record for record in records},
        )

    def submit_pending_abbreviation(self, **kwargs):
        return {
            "abbr": kwargs["abbr"],
            "status": "PENDING_CREATED",
            "pending_id": "pending-1",
            "has_suggested": False,
        }


class FakeUserRepository:
    def __init__(self):
        self.users = {
            "admin-1": {
                "id": "admin-1",
                "username": "admin_main",
                "email": "admin@vietnormalizer.local",
                "roles": ["admin"],
                "is_active": True,
                "created_at": "2026-04-01T00:00:00+00:00",
                "updated_at": "2026-04-01T00:00:00+00:00",
            },
            "user-1": {
                "id": "user-1",
                "username": "demo_user_01",
                "email": "demo01@example.com",
                "roles": ["user"],
                "is_active": True,
                "created_at": "2026-04-02T00:00:00+00:00",
                "updated_at": "2026-04-02T00:00:00+00:00",
            },
        }

    def is_ready(self):
        return True

    def list_users(self):
        return list(self.users.values())

    def find_by_id(self, user_id):
        return self.users.get(user_id)

    def find_by_identifier(self, identifier):
        cleaned = identifier.strip().lower()
        for user in self.users.values():
            if user["username"].lower() == cleaned or user["email"].lower() == cleaned:
                return user
        return None

    def delete_user(self, user_id):
        user = self.users.get(user_id)
        if not user:
            raise ValueError("USER_NOT_FOUND")
        if "admin" in user["roles"]:
            raise ValueError("ADMIN_USER_DELETE_FORBIDDEN")
        del self.users[user_id]
        return user


class FakeHistoryRepository:
    def __init__(self):
        self.entries = {
            "admin-1": [
                {
                    "id": "history-admin-1",
                    "input_text": "hn di hop",
                    "output_text": "hom nay di hop",
                    "error_types": ["ABBREVIATION"],
                    "model_used": None,
                    "from_cache": False,
                    "latency_ms": 12.0,
                    "domain": "general",
                    "source_kind": "web_live",
                    "user_id": "admin-1",
                    "username_snapshot": "admin_main",
                    "created_at": "2026-04-18T00:00:00+00:00",
                }
            ],
            "user-1": [
                {
                    "id": "history-user-1",
                    "input_text": "dk the",
                    "output_text": "dang ky the",
                    "error_types": ["ABBREVIATION"],
                    "model_used": None,
                    "from_cache": False,
                    "latency_ms": 15.0,
                    "domain": "general",
                    "source_kind": "web_live",
                    "user_id": "user-1",
                    "username_snapshot": "demo_user_01",
                    "created_at": "2026-04-18T00:01:00+00:00",
                }
            ],
        }

    def is_ready(self):
        return True

    def list_history(self, user_id=None, limit=30):
        if user_id:
            return self.entries.get(user_id, [])[:limit]
        all_entries = []
        for records in self.entries.values():
            all_entries.extend(records)
        return all_entries[:limit]

    def log_normalization(
        self,
        input_text,
        output_text,
        error_types,
        model_used=None,
        from_cache=False,
        latency_ms=None,
        domain="general",
        source_kind="web_live",
        username_snapshot=None,
        user_id=None,
    ):
        entry = {
            "id": "history-created-1",
            "input_text": input_text,
            "output_text": output_text,
            "error_types": list(error_types),
            "model_used": model_used,
            "from_cache": from_cache,
            "latency_ms": latency_ms,
            "domain": domain,
            "source_kind": source_kind,
            "user_id": user_id,
            "username_snapshot": username_snapshot,
            "created_at": "2026-04-18T00:02:00+00:00",
        }
        self.entries.setdefault(user_id or "anonymous", []).insert(0, entry)
        return entry

    def delete_history_entry(self, history_id, user_id=None):
        entries = self.entries.get(user_id or "", [])
        for index, entry in enumerate(entries):
            if entry["id"] == history_id:
                return entries.pop(index)
        raise ValueError("HISTORY_NOT_FOUND")


class FakeSessionRepository:
    def __init__(self):
        self.valid_tokens = set()
        self.revoked_user_ids = []

    def is_token_valid(self, token):
        return token in self.valid_tokens

    def get_active_sessions(self, user_id):
        return [
            {"id": "session-1", "user_id": user_id, "created_at": None, "expires_at": None}
        ]

    def revoke_all_user_sessions(self, user_id, reason="revoke_all"):
        self.revoked_user_ids.append((user_id, reason))
        count = len(self.valid_tokens)
        self.valid_tokens.clear()
        return count


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(auth_secret="test-secret")
        self.auth_service = FakeAuthService(self.settings)
        self.pending_service = FakePendingService()
        self.user_repository = FakeUserRepository()
        self.history_repository = FakeHistoryRepository()
        self.session_repository = FakeSessionRepository()
        self.app = create_app()
        self.app.dependency_overrides[_get_auth_service] = lambda: self.auth_service
        self.app.dependency_overrides[_get_pending_service] = lambda: self.pending_service
        self.app.dependency_overrides[_get_user_repository] = lambda: self.user_repository
        self.app.dependency_overrides[_get_history_repository] = lambda: self.history_repository
        self.app.dependency_overrides[_get_session_repository] = lambda: self.session_repository
        self.app.dependency_overrides[get_app_settings] = lambda: self.settings
        self.app.dependency_overrides[get_current_user] = lambda: {
            "id": "admin-1",
            "username": "admin_main",
            "email": "admin@vietnormalizer.local",
            "roles": ["admin"],
            "is_active": True,
        }
        self.client = TestClient(self.app)

    def _issue_token(self, user_id="admin-1"):
        user = self.user_repository.users[user_id]
        token = create_access_token(
            subject=user_id,
            claims={
                "username": user["username"],
                "email": user["email"],
                "roles": user["roles"],
            },
            settings=self.settings,
        ).token
        self.session_repository.valid_tokens.add(token)
        return token

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_register_returns_token_payload(self):
        response = self.client.post(
            "/api/auth/register",
            json={"username": "demo", "email": "demo@example.com", "password": "Secret@123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["accessToken"])

    def test_me_accepts_active_session_token_by_subject(self):
        del self.app.dependency_overrides[get_current_user]
        token = self._issue_token("admin-1")

        response = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "admin-1")

    def test_me_rejects_revoked_session_token(self):
        del self.app.dependency_overrides[get_current_user]
        token = self._issue_token("admin-1")
        self.session_repository.valid_tokens.remove(token)

        response = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 401)

    def test_me_rejects_inactive_user_even_with_valid_session(self):
        del self.app.dependency_overrides[get_current_user]
        self.user_repository.users["admin-1"]["is_active"] = False
        token = self._issue_token("admin-1")

        response = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(response.status_code, 401)

    def test_login_and_live_normalize(self):
        login_response = self.client.post(
            "/api/auth/login",
            json={"identifier": "admin_main", "password": "Admin@123"},
        )
        token = login_response.json()["accessToken"]

        response = self.client.post(
            "/api/normalize/live",
            json={"text": "hom nay di dk the ngan hang pk", "resolutionOverrides": {}},
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            data["variants"][0]["output"],
            "Hôm nay đi dk thẻ ngân hàng phai khong",
        )
        self.assertEqual(
            data["variants"][1]["output"],
            "Hôm nay đi dang ky thẻ ngân hàng phai khong",
        )
        self.assertTrue(data.get("diacriticApplied"))
        self.assertEqual(data["expandedAbbreviations"][0]["abbr"], "pk")
        span = data["expandedAbbreviations"][0]
        self.assertEqual(
            data["primaryOutput"][span["start"] : span["end"]],
            span["expanded"],
        )

    def test_live_normalize_dataset_only_does_not_construct_or_call_ai(self):
        from unittest.mock import patch

        with patch("app.api.routes.get_semantic_verifier") as verifier_factory:
            response = self.client.post(
                "/api/normalize/live",
                json={"text": "hom nay di dk the ngan hang pk", "allowAI": False},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["semanticStatusReason"], "dataset_only")
        verifier_factory.assert_not_called()

    def test_disambiguate_requires_ai_consent_before_provider_access(self):
        from unittest.mock import patch

        with patch("app.api.routes.get_disambiguator") as disambiguator_factory:
            response = self.client.post(
                "/api/normalize/disambiguate",
                json={"text": "hom nay dk", "ambiguities": [], "allowAI": False},
            )

        self.assertEqual(response.status_code, 409)
        disambiguator_factory.assert_not_called()

    def test_shared_ai_budget_on_authenticated_live_requests(self):
        import json
        import tempfile
        from dataclasses import replace
        from pathlib import Path
        from unittest.mock import patch
        from app.ai.admission import BudgetedClient
        from app.ai.client import AIResponse
        from app.ai.semantic_verifier import SemanticVerifier

        class FakeAI:
            calls = 0

            def is_available(self):
                return True

            async def complete(self, request):
                self.calls += 1
                source = request.prompt.split('Output hiện tại cần kiểm tra:\n"')[1].split('"\n')[0]
                return AIResponse(json.dumps({"verified_text": source, "confidence": 0.9}), 1, 0, "fake")

        with tempfile.TemporaryDirectory() as directory:
            self.settings = replace(self.settings, ai_budget_path=str(Path(directory) / "budget.sqlite3"),
                                    ai_user_requests_per_window=1, ai_requests_per_window=2,
                                    diacritic_auto_detect=False, ai_max_retries=0)
            del self.app.dependency_overrides[get_current_user]
            fake = FakeAI()
            verifier = SemanticVerifier(BudgetedClient(fake, self.settings, "fake-account"))
            admin = {"Authorization": "Bearer " + self._issue_token("admin-1")}
            user = {"Authorization": "Bearer " + self._issue_token("user-1")}
            with patch("app.api.routes.get_semantic_verifier", return_value=verifier):
                for _ in range(2):
                    response = self.client.post("/api/normalize/live", headers=admin,
                                                json={"text": "dk", "allowAI": True})
                    self.assertEqual(response.status_code, 200)
                self.assertEqual(fake.calls, 1)
                denied = self.client.post("/api/normalize/live", headers=admin,
                                          json={"text": "dk hôm nay", "allowAI": True})
                self.assertEqual(denied.json()["semanticStatus"], "quota")
                allowed = self.client.post("/api/normalize/live", headers=user,
                                           json={"text": "dk", "allowAI": True})
                self.assertEqual(allowed.status_code, 200)
                self.assertNotEqual(allowed.json()["semanticStatus"], "quota")
                self.assertEqual(fake.calls, 2)

    def test_semantic_verification_runs_for_completed_long_typing_text(self):
        long_text = (
            "nghe noi hom nay m k dc vui a? "
            "co f m vua ct ny hay k? "
            "T nghe mn ban tan nhu the nhung k biet co dung k."
        )
        result = _SemanticProbe(
            diacritic_applied=True,
            diacritic_changes=[("nghe", "nghﾄ・"), ("noi", "nﾃｳi")],
        )

        self.assertTrue(
            _should_apply_semantic_verification(
                input_method="typing",
                text=long_text,
                result=result,
                settings=Settings(semantic_verify_typing_min_chars=80),
            )
        )

    def test_semantic_verification_runs_for_incomplete_typing_text(self):
        result = _SemanticProbe(
            diacritic_applied=True,
            diacritic_changes=[("nghe", "nghﾄ・"), ("noi", "nﾃｳi")],
        )

        self.assertTrue(
            _should_apply_semantic_verification(
                input_method="typing",
                text="nghe noi hom nay m k dc vui",
                result=result,
                settings=Settings(),
            )
        )

    def test_semantic_verification_runs_for_long_paste_with_signal(self):
        self.assertTrue(
            _should_apply_semantic_verification(
                input_method="paste",
                text="nghe noi hom nay m k dc vui a? co f m vua ct ny hay k?",
                result=_SemanticProbe(ambiguities=[{"abbr": "ct"}]),
                settings=Settings(semantic_verify_paste_min_chars=20),
            )
        )

    def test_semantic_verification_reviews_short_paste_without_signal(self):
        self.assertTrue(
            _should_apply_semantic_verification(
                input_method="paste",
                text="short text",
                result=_SemanticProbe(),
                settings=Settings(),
            )
        )

    def test_pending_routes_require_admin(self):
        self.app.dependency_overrides[get_current_user] = lambda: {
            "id": "user-1",
            "username": "demo_user",
            "email": "user@example.com",
            "roles": ["user"],
            "is_active": True,
        }
        response = self.client.get("/api/pending")
        self.assertEqual(response.status_code, 403)

    def test_regular_user_cannot_add_personal_abbreviation_meaning(self):
        self.app.dependency_overrides[get_current_user] = lambda: {
            "id": "user-1",
            "username": "demo_user",
            "email": "user@example.com",
            "roles": ["user"],
            "is_active": True,
        }

        response = self.client.post(
            "/api/abbreviations/user-meanings",
            json={"abbr": "dk", "meaning": "dieu kien"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.pending_service.user_meaning_calls, [])

    def test_admin_user_meaning_endpoint_approves_immediately(self):
        response = self.client.post(
            "/api/abbreviations/user-meanings",
            json={"abbr": "dk", "meaning": "dieu kien"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "APPROVED")
        self.assertEqual(self.pending_service.admin_meaning_calls[0]["reviewer"], "admin_main")
        self.assertTrue(self.pending_service.admin_meaning_calls[0]["approve_immediately"])
        self.assertEqual(self.pending_service.user_meaning_calls, [])

    def test_history_route_returns_current_user_entries(self):
        response = self.client.get("/api/history")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["user_id"], "admin-1")

    def test_history_of_another_account_is_not_exposed(self):
        for method, path in (
            ("get", "/api/users/user-1/history"),
            ("delete", "/api/users/user-1/history/history-user-1"),
        ):
            for role in ("admin", "user"):
                with self.subTest(method=method, path=path, role=role):
                    self.app.dependency_overrides[get_current_user] = lambda role=role: {
                        "id": "admin-1" if role == "admin" else "user-1",
                        "username": "admin_main" if role == "admin" else "demo_user_01",
                        "email": "admin@example.com" if role == "admin" else "demo@example.com",
                        "roles": [role],
                        "is_active": True,
                    }
                    response = getattr(self.client, method)(path)
                    self.assertEqual(response.status_code, 404)

    def test_history_reads_and_deletes_are_scoped_to_authenticated_owner(self):
        for user_id, role, foreign_history_id in (
            ("admin-1", "admin", "history-user-1"),
            ("user-1", "user", "history-admin-1"),
        ):
            with self.subTest(user_id=user_id):
                self.app.dependency_overrides[get_current_user] = lambda user_id=user_id, role=role: {
                    "id": user_id,
                    "username": "admin_main" if role == "admin" else "demo_user_01",
                    "email": "admin@example.com" if role == "admin" else "demo@example.com",
                    "roles": [role],
                    "is_active": True,
                }
                list_response = self.client.get("/api/history")
                self.assertEqual(list_response.status_code, 200)
                self.assertTrue(all(entry["user_id"] == user_id for entry in list_response.json()))

                delete_response = self.client.delete(f"/api/history/{foreign_history_id}")
                self.assertEqual(delete_response.status_code, 404)

    def test_admin_can_create_history_entry(self):
        response = self.client.post(
            "/api/history",
            json={
                "input_text": "hn di dk",
                "output_text": "hom nay di dang ky",
                "error_types": ["ABBREVIATION"],
                "latency_ms": 18.5,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user_id"], "admin-1")
        self.assertEqual(self.history_repository.entries["admin-1"][0]["input_text"], "hn di dk")

    def test_current_user_can_delete_history_entry(self):
        response = self.client.delete("/api/history/history-admin-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.history_repository.entries["admin-1"], [])

    def test_admin_can_delete_regular_user(self):
        response = self.client.delete("/api/users/user-1")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("user-1", self.user_repository.users)

    def test_admin_can_save_dictionary_entry(self):
        response = self.client.put(
            "/api/abbreviations/vch",
            json={
                "expanded": "van chuong hoc",
                "alternative_expansions": ["van chuong hoa"],
                "domain": "general",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["abbr"], "vch")
        self.assertEqual(response.json()["expanded"], "van chuong hoc")

    def test_dictionary_list_returns_all_domains_by_default(self):
        self.pending_service.saved_abbreviations["vc-text"] = {
            "id": "abbr-vc-text",
            "abbr": "vc",
            "expanded": "viec",
            "alternative_expansions": ["vo chong"],
            "domain": "text_normalization",
            "source": "json_seed",
            "created_at": None,
            "approved_by": "seed",
        }

        response = self.client.get("/api/abbreviations")
        general_response = self.client.get("/api/abbreviations?domain=general")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {(record["abbr"], record["domain"]) for record in response.json()},
            {("dk", "general"), ("vc", "text_normalization")},
        )
        self.assertEqual(general_response.status_code, 200)
        self.assertEqual(
            {(record["abbr"], record["domain"]) for record in general_response.json()},
            {("dk", "general")},
        )

    def test_dictionary_list_is_available_when_sql_is_not_ready(self):
        self.pending_service.ready = False

        response = self.client.get("/api/abbreviations")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["abbr"], "dk")

    def test_admin_cannot_delete_admin_account(self):
        response = self.client.delete("/api/users/admin-1")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Tai khoan admin khong the bi xoa.")

    def test_assign_role_route_is_disabled(self):
        response = self.client.post("/api/users/user-1/roles", json={"roleName": "admin"})

        self.assertEqual(response.status_code, 405)

    def test_preference_payload_requires_value(self):
        response = self.client.put("/api/preferences/editor.theme", json={"category": "ui"})

        self.assertEqual(response.status_code, 422)

    def test_phrase_override_create_rejects_invalid_priority_type(self):
        response = self.client.post(
            "/api/admin/phrase-overrides",
            json={
                "phrase_key": "dk hp",
                "phrase_value": "dang ky hoc phan",
                "priority": "high",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_phrase_override_update_rejects_negative_priority(self):
        response = self.client.put(
            "/api/admin/phrase-overrides/override-1",
            json={"priority": -1},
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
