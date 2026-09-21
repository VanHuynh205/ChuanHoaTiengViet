"""End-to-end test: /api/normalize/live returns phraseMatches.

Builds a FastAPI TestClient with a fake pending service that publishes a
phrase override, hits the live endpoint, and asserts the new
``phraseMatches`` field is populated.
"""

from __future__ import annotations

import unittest

import pytest

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - optional dependency in early setup
    TestClient = None  # type: ignore[assignment]

from app.api.dependencies import get_app_settings, get_current_user
from app.api.routes import _get_pending_service
from app.api.server import create_app
from app.config import Settings
from app.data_manager.pending_service import LiveNormalizationData


class FakePhrasePending:
    def __init__(self) -> None:
        self.submissions: list[dict] = []

    def db_is_ready(self) -> bool:
        return False

    def get_approved_abbreviations(self):
        return {}

    def get_dictionary_words(self):
        return {"hôm", "nay", "xong", "rồi"}

    def list_approved_abbreviations(self, abbr=None, domain="general"):
        return []

    def get_live_normalization_data(self, domain: str = "general", user_id=None):
        return LiveNormalizationData(
            abbreviations={},
            dictionary_words=self.get_dictionary_words(),
            approved_details={},
            phrase_overrides={
                "đk hp": {
                    "expanded": "đăng ký học phần",
                    "source": "override",
                    "confidence": 1.0,
                }
            },
            db_phrases={},
            mined_phrases={},
        )

    def submit_pending_abbreviation(self, **kwargs):
        self.submissions.append(kwargs)
        return {
            "abbr": kwargs["abbr"],
            "status": "PENDING_CREATED",
            "pending_id": "p-1",
            "has_suggested": False,
        }


@pytest.mark.skipif(TestClient is None, reason="FastAPI not installed")
class PhraseLiveRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings()
        self.pending_service = FakePhrasePending()
        self.app = create_app()

        self.app.dependency_overrides[_get_pending_service] = lambda: self.pending_service
        self.app.dependency_overrides[get_app_settings] = lambda: self.settings
        self.app.dependency_overrides[get_current_user] = lambda: {
            "id": "admin-1",
            "username": "admin_main",
            "email": "admin@vietnormalizer.local",
            "roles": ["admin"],
            "is_active": True,
        }
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_live_normalize_returns_phrase_matches(self) -> None:
        response = self.client.post(
            "/api/normalize/live",
            json={"text": "Hôm nay đk hp xong rồi.", "resolutionOverrides": {}},
            headers={"Authorization": "Bearer test"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "phraseMatches" in body
        matches = body["phraseMatches"]
        assert len(matches) == 1
        match = matches[0]
        assert match["matched"] == "đk hp"
        assert match["expanded"] == "đăng ký học phần"
        assert match["source"] == "override"
        assert "đăng ký học phần" in body["primaryOutput"]
