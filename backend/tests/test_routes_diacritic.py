import pytest

try:
    from fastapi.testclient import TestClient
except ImportError:
    pytest.skip("FastAPI not installed", allow_module_level=True)

from app.api.routes import router


def _make_client():
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestRestoreDiacriticEndpoint:
    """Smoke tests for POST /api/normalize/restore-diacritic.

    These verify request/response shape only — full AI coverage is in
    test_diacritic_restorer.py. The endpoint requires authentication,
    so without a valid token these should return 401/403.
    """

    def test_unauthenticated_returns_error(self):
        client = _make_client()
        resp = client.post(
            "/api/normalize/restore-diacritic",
            json={"text": "toi di hoc", "force": False},
        )
        assert resp.status_code in (401, 403)

    def test_missing_text_field_returns_auth_or_validation_error(self):
        client = _make_client()
        resp = client.post(
            "/api/normalize/restore-diacritic",
            json={"force": False},
        )
        assert resp.status_code in (401, 422)


class TestDisambiguateEndpoint:

    def test_unauthenticated_returns_error(self):
        client = _make_client()
        resp = client.post(
            "/api/normalize/disambiguate",
            json={"text": "toi di dk", "ambiguities": []},
        )
        assert resp.status_code in (401, 403)

    def test_missing_text_field(self):
        client = _make_client()
        resp = client.post(
            "/api/normalize/disambiguate",
            json={"ambiguities": []},
        )
        assert resp.status_code in (401, 422)
