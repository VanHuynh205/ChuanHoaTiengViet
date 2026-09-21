"""Tests for app.ai.client provider implementations and factory wiring."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from typing import Any

import pytest
import respx
from tenacity import wait_none

from app.ai.client import (
    NVIDIA_BASE_URL,
    AIRequest,
    AIResponse,
    NvidiaClient,
    NullClient,
    build_default_client,
    reset_rate_limit_breaker,
)
from app.ai.errors import (
    AIAuthError,
    AINetworkDisabledError,
    AIParseError,
)
from app.config import Settings


@pytest.fixture(autouse=True)
def _reset_ai_state() -> None:
    """Reset the circuit breaker and client cache before every test."""
    reset_rate_limit_breaker()


def _settings(**overrides: Any) -> Settings:
    """Build a Settings instance with explicit AI overrides for testing."""
    base: dict[str, Any] = dict(
        ai_provider="none",
        nvidia_api_key="",
        nvidia_model="z-ai/glm-5.1",
        nvidia_base_url=NVIDIA_BASE_URL,
        nvidia_enable_thinking=True,
        nvidia_clear_thinking=False,
        ai_timeout_seconds=10,
        ai_max_retries=2,
        ai_disable_network=False,
        ai_rate_limit_cooldown_seconds=60,
    )
    base.update(overrides)
    s = Settings()
    return replace(s, **base)


def _nvidia_url() -> str:
    return f"{NVIDIA_BASE_URL}/chat/completions"


def _good_payload(text: str = "ok", total_tokens: int = 12) -> dict[str, Any]:
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}}],
        "usageMetadata": {"totalTokenCount": total_tokens},
    }


def _good_chat_payload(text: str = "ok", total_tokens: int = 12) -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": text, "reasoning_content": "hidden"}}],
        "usage": {"total_tokens": total_tokens},
    }


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_ai_request_defaults() -> None:
    req = AIRequest(prompt="hi")
    assert req.prompt == "hi"
    assert req.system is None
    assert req.max_tokens == 1024
    assert req.temperature == pytest.approx(0.1)
    assert req.json_mode is False


@pytest.mark.unit
def test_ai_response_is_frozen() -> None:
    resp = AIResponse(text="x", tokens_used=1, latency_ms=2, model="m")
    with pytest.raises((AttributeError, TypeError)):
        resp.text = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# NullClient
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_null_client_is_unavailable() -> None:
    null = NullClient(model="any")
    assert null.is_available() is False
    assert null.model == "any"


@pytest.mark.unit
def test_null_client_complete_raises() -> None:
    null = NullClient()

    async def run() -> None:
        with pytest.raises(AINetworkDisabledError):
            await null.complete(AIRequest(prompt="hi"))

    asyncio.run(run())


# ---------------------------------------------------------------------------
# NvidiaClient
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_nvidia_client_requires_api_key() -> None:
    with pytest.raises(ValueError):
        NvidiaClient(api_key="", model="z-ai/glm-5.1")


@pytest.mark.unit
def test_nvidia_client_is_available() -> None:
    client = NvidiaClient(api_key="k", model="z-ai/glm-5.1")
    assert client.is_available() is True
    assert client.model == "z-ai/glm-5.1"


@pytest.mark.ai
def test_nvidia_client_success() -> None:
    model = "z-ai/glm-5.1"

    async def run() -> None:
        async with respx.mock(assert_all_called=True) as router:
            route = router.post(_nvidia_url()).respond(json=_good_chat_payload("xin chào", 33))
            client = NvidiaClient(
                api_key="key",
                model=model,
                max_retries=0,
                wait_strategy=wait_none(),
            )

            resp = await client.complete(AIRequest(prompt="hi"))

            assert resp.text == "xin chào"
            assert resp.tokens_used == 33
            assert resp.model == model
            assert resp.latency_ms >= 0
            sent = route.calls.last.request
            assert sent.headers["authorization"] == "Bearer key"
            body = json.loads(sent.read().decode("utf-8"))
            assert body["model"] == model
            assert body["messages"] == [{"role": "user", "content": "hi"}]
            assert body["stream"] is False
            assert body["chat_template_kwargs"] == {
                "enable_thinking": True,
                "clear_thinking": False,
            }

    asyncio.run(run())


@pytest.mark.ai
def test_nvidia_client_passes_system_json_mode_and_generation_options() -> None:
    async def run() -> None:
        async with respx.mock() as router:
            route = router.post(_nvidia_url()).respond(json=_good_chat_payload())
            client = NvidiaClient(
                api_key="k",
                model="z-ai/glm-5.1",
                max_retries=0,
                wait_strategy=wait_none(),
            )

            await client.complete(
                AIRequest(
                    prompt="hi",
                    system="you are helpful",
                    max_tokens=256,
                    temperature=0.2,
                    json_mode=True,
                )
            )

            body = json.loads(route.calls.last.request.read().decode("utf-8"))
            assert body["messages"] == [
                {"role": "system", "content": "you are helpful"},
                {"role": "user", "content": "hi"},
            ]
            assert body["max_tokens"] == 256
            assert body["temperature"] == pytest.approx(0.2)
            assert body["response_format"] == {"type": "json_object"}

    asyncio.run(run())


@pytest.mark.ai
def test_nvidia_client_auth_error() -> None:
    async def run() -> None:
        async with respx.mock() as router:
            router.post(_nvidia_url()).respond(status_code=401, json={"error": "no"})
            client = NvidiaClient(
                api_key="k",
                model="z-ai/glm-5.1",
                max_retries=0,
                wait_strategy=wait_none(),
            )
            with pytest.raises(AIAuthError):
                await client.complete(AIRequest(prompt="hi"))

    asyncio.run(run())


@pytest.mark.ai
def test_nvidia_client_missing_choices_raises_parse_error() -> None:
    async def run() -> None:
        async with respx.mock() as router:
            router.post(_nvidia_url()).respond(json={"choices": []})
            client = NvidiaClient(
                api_key="k",
                model="z-ai/glm-5.1",
                max_retries=0,
                wait_strategy=wait_none(),
            )
            with pytest.raises(AIParseError):
                await client.complete(AIRequest(prompt="hi"))

    asyncio.run(run())


# ---------------------------------------------------------------------------
# build_default_client
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_default_client_disabled_returns_null() -> None:
    s = _settings(ai_disable_network=True, ai_provider="nvidia", nvidia_model="nvidia/nemotron-3.5-lightning-30b-a3b")
    client = build_default_client(s)
    assert isinstance(client, NullClient)
    assert client.model == "nvidia/nemotron-3.5-lightning-30b-a3b"


@pytest.mark.unit
def test_build_default_client_provider_none_returns_null() -> None:
    s = _settings(ai_provider="none")
    client = build_default_client(s)
    assert isinstance(client, NullClient)


@pytest.mark.unit
def test_build_default_client_blank_provider_returns_null() -> None:
    s = _settings(ai_provider="")
    client = build_default_client(s)
    assert isinstance(client, NullClient)


@pytest.mark.unit
def test_build_default_client_nvidia_without_key_returns_null() -> None:
    s = _settings(ai_provider="nvidia", nvidia_api_key="")
    client = build_default_client(s)
    assert isinstance(client, NullClient)
    assert client.model == "z-ai/glm-5.1"


@pytest.mark.unit
def test_build_default_client_nvidia_with_key_returns_nvidia() -> None:
    from app.ai.admission import BudgetedClient
    s = _settings(ai_provider="nvidia", nvidia_api_key="real-key")
    client = build_default_client(s)
    assert isinstance(client, BudgetedClient)
    assert client.model == "z-ai/glm-5.1"
    assert client.is_available() is True


@pytest.mark.unit
def test_build_default_client_unknown_provider_returns_null() -> None:
    s = _settings(ai_provider="openai")
    client = build_default_client(s)
    assert isinstance(client, NullClient)
