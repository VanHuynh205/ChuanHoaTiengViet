"""Startup-time and middleware guarantees that the rest of the suite assumes."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.server import BodySizeLimitMiddleware
from app.config import AUTH_SECRET_DEV_FALLBACK, Settings


def _app_with_limit(max_body_bytes: int) -> FastAPI:
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=max_body_bytes)

    @app.post("/echo")
    async def echo(payload: dict):  # pragma: no cover - exercised through the client
        return {"size": len(str(payload))}

    return app


def test_oversized_body_is_rejected_before_reaching_the_handler():
    client = TestClient(_app_with_limit(2048))

    assert client.post("/echo", json={"t": "a" * 100}).status_code == 200

    too_big = client.post("/echo", json={"t": "a" * 8000})
    assert too_big.status_code == 413
    assert "qua lon" in too_big.json()["detail"]


def test_zero_limit_disables_the_check():
    client = TestClient(_app_with_limit(0))
    assert client.post("/echo", json={"t": "a" * 8000}).status_code == 200


@pytest.mark.parametrize(
    "settings, expected_fragment",
    [
        (
            Settings(auth_secret=AUTH_SECRET_DEV_FALLBACK, app_env="development"),
            "published development sentinel",
        ),
        (Settings(auth_secret="too-short", app_env="development"), "at least 32 characters"),
        (
            Settings(
                auth_secret="k" * 40, app_env="production", web_origin="http://localhost:5173"
            ),
            "localhost",
        ),
        (
            Settings(auth_secret="k" * 40, app_env="production", web_origin="https://x.dev/*"),
            "'*'",
        ),
        (
            Settings(auth_secret="k" * 40, app_env="production", cli_assume_admin=True,
                     web_origin="https://app.example.com", ai_provider="none"),
            "CLI_ASSUME_ADMIN",
        ),
    ],
)
def test_fatal_configurations_are_reported(settings, expected_fragment):
    """These checks must fire regardless of APP_ENV where noted.

    They used to sit behind ``if self.is_production``, so forgetting to set
    APP_ENV silently disabled every one of them.
    """
    errors = settings.validate()
    assert any(expected_fragment in error for error in errors), errors


def test_dev_sentinel_can_be_accepted_only_with_an_explicit_opt_in():
    settings = Settings(
        auth_secret=AUTH_SECRET_DEV_FALLBACK,
        app_env="development",
        allow_dev_auth_secret=True,
    )
    assert settings.validate() == []


def test_opt_in_is_still_rejected_in_production():
    settings = Settings(
        auth_secret="k" * 40,
        app_env="production",
        allow_dev_auth_secret=True,
        web_origin="https://app.example.com",
        ai_provider="none",
    )
    assert any("ALLOW_DEV_AUTH_SECRET" in error for error in settings.validate())
