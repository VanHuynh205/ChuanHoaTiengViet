"""AI client abstraction for NVIDIA models.

The factory ``build_default_client`` is the single entry point used by the
rest of the app. It returns:

* ``NullClient`` when the network is disabled, when the provider is unknown,
  or when the configured provider is missing credentials. Callers that
  receive ``NullClient`` can fall back to rule-based logic.
* ``NvidiaClient`` for the configured NVIDIA model.

The protocol stays minimal (``complete`` + ``is_available``) so additional
providers can be added by satisfying it without touching call sites.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_none,
)

from app.ai.errors import (
    AIAuthError,
    AINetworkDisabledError,
    AINetworkError,
    AIParseError,
    AIRateLimitError,
    AITimeoutError,
)
from app.config import Settings

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AI usage counters (observability, not billing)
# ---------------------------------------------------------------------------


class AIUsageStats:
    """Thread-safe counters for AI call volume and token consumption."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._call_count = 0
        self._tokens_used = 0
        self._rate_limited_count = 0
        self._error_count = 0

    def record_call(self, tokens_used: int) -> None:
        with self._lock:
            self._call_count += 1
            self._tokens_used += tokens_used

    def record_rate_limit(self) -> None:
        with self._lock:
            self._rate_limited_count += 1

    def record_error(self) -> None:
        with self._lock:
            self._error_count += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "call_count": self._call_count,
                "tokens_used": self._tokens_used,
                "rate_limited_count": self._rate_limited_count,
                "error_count": self._error_count,
            }

    def reset(self) -> None:
        with self._lock:
            self._call_count = 0
            self._tokens_used = 0
            self._rate_limited_count = 0
            self._error_count = 0


_usage_stats = AIUsageStats()


def get_ai_usage_stats() -> dict[str, int]:
    """Return a snapshot of AI call counters since last reset."""
    return _usage_stats.snapshot()


def reset_ai_usage_stats() -> None:
    """Reset AI usage counters. For tests or session boundaries."""
    _usage_stats.reset()


# ---------------------------------------------------------------------------
# Rate-limit circuit breaker
# ---------------------------------------------------------------------------
# When the upstream provider returns HTTP 429, the breaker trips and all
# subsequent AI calls are short-circuited for a cooldown period.  This
# prevents the thundering-herd effect where many concurrent requests each
# burn through their own retry budgets against an already-exhausted quota.
# ---------------------------------------------------------------------------


class _RateLimitCircuitBreaker:
    """Module-level circuit breaker that trips on HTTP 429 responses."""

    def __init__(self, default_cooldown: float = 60.0) -> None:
        self._default_cooldown = default_cooldown
        self._open_until: float = 0.0  # monotonic timestamp
        self._lock = threading.Lock()

    def set_default_cooldown(self, default_cooldown: float) -> None:
        """Update the default cooldown; values <= 0 disable the breaker."""
        with self._lock:
            self._default_cooldown = max(0.0, float(default_cooldown))
            if self._default_cooldown == 0:
                self._open_until = 0.0

    def trip(self, retry_after: float | None = None) -> None:
        """Record a 429 event and open the circuit."""
        with self._lock:
            if self._default_cooldown <= 0:
                self._open_until = 0.0
                return
            cooldown = (
                retry_after
                if retry_after is not None and retry_after > 0
                else self._default_cooldown
            )
            new_open_until = time.monotonic() + cooldown
            if new_open_until > self._open_until:
                self._open_until = new_open_until
                LOGGER.warning(
                    "AI rate-limit circuit breaker tripped; " "skipping AI calls for %.0f seconds",
                    cooldown,
                )

    def is_open(self) -> bool:
        """Return ``True`` when calls should be blocked (circuit is open)."""
        with self._lock:
            if self._default_cooldown <= 0:
                return False
            return time.monotonic() < self._open_until

    @property
    def remaining_seconds(self) -> float:
        with self._lock:
            return max(0.0, self._open_until - time.monotonic())

    def reset(self) -> None:
        """Close the circuit (allow calls again). Intended for testing."""
        with self._lock:
            self._open_until = 0.0


_DEFAULT_COOLDOWN = float(os.getenv("AI_RATE_LIMIT_COOLDOWN", "60"))
_rate_limit_breaker = _RateLimitCircuitBreaker(default_cooldown=_DEFAULT_COOLDOWN)
_client_cache: dict[Settings, AIClient] = {}
_client_cache_lock = threading.Lock()


def configure_rate_limit_breaker(default_cooldown: float) -> None:
    """Configure the global AI rate-limit circuit breaker."""
    _rate_limit_breaker.set_default_cooldown(default_cooldown)


def reset_rate_limit_breaker() -> None:
    """Reset the global circuit breaker, client cache, and usage stats. For tests only."""
    _rate_limit_breaker.set_default_cooldown(_DEFAULT_COOLDOWN)
    _rate_limit_breaker.reset()
    _usage_stats.reset()
    with _client_cache_lock:
        _client_cache.clear()


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Parse the ``Retry-After`` header as seconds, or ``None``."""
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(1.0, float(value))
    except ValueError:
        return None


@dataclass(frozen=True)
class AIRequest:
    """Single shot completion request."""

    prompt: str
    system: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.1
    json_mode: bool = False
    # Local cache/coalescing identity; not part of the provider request body.
    cache_namespace: str = ""
    enable_thinking: bool | None = None


@dataclass(frozen=True)
class AIResponse:
    """Provider response normalised to a common shape."""

    text: str
    tokens_used: int
    latency_ms: int
    model: str
    fallback_used: bool = False


class AIClient(Protocol):
    async def complete(self, request: AIRequest) -> AIResponse: ...

    def is_available(self) -> bool: ...


class NullClient:
    """No-op client used when AI is disabled.

    All ``complete`` calls raise ``AINetworkDisabledError`` so the caller
    can deterministically fall back to rule-based logic.
    """

    def __init__(self, model: str = "null") -> None:
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, request: AIRequest) -> AIResponse:
        raise AINetworkDisabledError(
            "AI provider disabled (AI_PROVIDER=none or AI_DISABLE_NETWORK=1)."
        )

    def is_available(self) -> bool:
        return False


class NvidiaClient:
    """Async OpenAI-compatible client for GLM models served by NVIDIA Build.

    The user-facing model target is ``z-ai/glm-5.1``. NVIDIA's OpenAI-compatible
    endpoint accepts the same chat-completions shape as the OpenAI SDK; the
    ``chat_template_kwargs`` field mirrors the sample NVIDIA Build code and
    enables model thinking without streaming reasoning back into app responses.
    """

    _RETRYABLE: tuple[type[BaseException], ...] = (AINetworkError,)

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: int = 10,
        max_retries: int = 2,
        base_url: str = NVIDIA_BASE_URL,
        enable_thinking: bool = True,
        clear_thinking: bool = False,
        client: httpx.AsyncClient | None = None,
        wait_strategy: Any = None,
    ) -> None:
        if not api_key:
            raise ValueError("NvidiaClient requires a non-empty api_key")
        self._api_key = api_key
        self._model = model
        connect_timeout = min(5.0, float(timeout_seconds))
        self._timeout = httpx.Timeout(float(timeout_seconds), connect=connect_timeout)
        self._max_retries = max(0, int(max_retries))
        self._base_url = base_url.rstrip("/")
        self._enable_thinking = enable_thinking
        self._clear_thinking = clear_thinking
        self._client = client
        self._wait_strategy = (
            wait_strategy
            if wait_strategy is not None
            else wait_exponential(multiplier=0.25, min=0.25, max=4.0)
        )

    @property
    def model(self) -> str:
        return self._model

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def complete(self, request: AIRequest) -> AIResponse:
        if _rate_limit_breaker.is_open():
            raise AIRateLimitError(
                f"AI rate-limit cooldown active "
                f"({_rate_limit_breaker.remaining_seconds:.0f}s remaining); "
                f"skipping NVIDIA call."
            )

        url = f"{self._base_url}/chat/completions"
        headers = {
            "authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }
        body = self._build_body(request)

        started = time.perf_counter()
        try:
            payload = await self._post_with_retry(url, headers, body)
        except httpx.TimeoutException as exc:
            _usage_stats.record_error()
            raise AITimeoutError(f"NVIDIA request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            _usage_stats.record_error()
            raise AINetworkError(f"NVIDIA transport error: {exc}") from exc
        latency_ms = int((time.perf_counter() - started) * 1000)
        response = self._parse_response(payload, latency_ms)
        _usage_stats.record_call(response.tokens_used)
        return response

    def _build_body(self, request: AIRequest) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})

        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": request.temperature,
            "top_p": 1,
            "max_tokens": request.max_tokens,
            "stream": False,
            "chat_template_kwargs": {
                # A per-request flag wins: the semantic verifier marks its
                # calls enable_thinking=False so a long review never spends
                # the deadline on hidden chain-of-thought.
                "enable_thinking": (
                    self._enable_thinking
                    if request.enable_thinking is None
                    else request.enable_thinking
                ),
                "clear_thinking": self._clear_thinking,
            },
        }
        if request.json_mode:
            body["response_format"] = {"type": "json_object"}
        if self._model.startswith(("deepseek-ai/", "mistralai/", "google/")):
            # These models use the standard chat contract, not the template
            # controls for GLM/Nemotron. Do not send another model's flags.
            body.pop("chat_template_kwargs", None)
        return body

    async def _post_with_retry(
        self,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
    ) -> dict[str, Any]:
        wait = self._wait_strategy if self._max_retries > 0 else wait_none()
        result: dict[str, Any] | None = None
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries + 1),
            wait=wait,
            retry=retry_if_exception_type(self._RETRYABLE),
            reraise=True,
        ):
            with attempt:
                result = await self._post_once(url, headers, body)
        if result is None:  # pragma: no cover - reraise=True guarantees exit on failure
            raise AINetworkError("NVIDIA retry loop exited without a response")
        return result

    async def _post_once(
        self,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
    ) -> dict[str, Any]:
        client = self._client
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.post(url, headers=dict(headers), json=dict(body))
        finally:
            if owns_client:
                await client.aclose()

        return self._handle_status(response)

    def _handle_status(self, response: httpx.Response) -> dict[str, Any]:
        status = response.status_code
        if status in (401, 403):
            raise AIAuthError(f"NVIDIA auth failed ({status}): {response.text[:200]}")
        if status == 429:
            _rate_limit_breaker.trip(_parse_retry_after(response))
            _usage_stats.record_rate_limit()
            raise AIRateLimitError(f"NVIDIA rate limit hit (429): {response.text[:200]}")
        if status in (500, 502, 503, 504):
            raise AINetworkError(f"NVIDIA transient error ({status}): {response.text[:200]}")
        if status >= 400:
            raise AINetworkError(f"NVIDIA unexpected status {status}: {response.text[:200]}")

        try:
            return response.json()
        except ValueError as exc:
            raise AIParseError(f"NVIDIA response was not JSON: {exc}") from exc

    def _parse_response(self, payload: Mapping[str, Any], latency_ms: int) -> AIResponse:
        try:
            choices = payload["choices"]
            message = choices[0]["message"]
            content = message.get("content", "")
            finish_reason = choices[0].get("finish_reason")
        except (KeyError, IndexError, TypeError) as exc:
            raise AIParseError(f"NVIDIA response missing choices/message: {payload}") from exc

        if finish_reason == "length":
            # A truncated completion cannot be trusted: the JSON the verifier
            # expects would be cut mid-string and silently lose the tail of
            # the user's text.
            raise AIParseError(
                "NVIDIA completion truncated (finish_reason=length); "
                "refusing a cut-off answer"
            )

        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "".join(
                str(part.get("text", "")) for part in content if isinstance(part, Mapping)
            )
        else:
            text = ""

        usage = payload.get("usage") or {}
        tokens_used = int(usage.get("total_tokens", 0) or 0)
        return AIResponse(
            text=text,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            model=self._model,
        )


def build_default_client(settings: Settings) -> AIClient:
    """Construct the configured NVIDIA client or a rule-based null client."""
    configure_rate_limit_breaker(settings.ai_rate_limit_cooldown_seconds)
    key = settings
    with _client_cache_lock:
        cached = _client_cache.get(key)
        if cached is not None:
            return cached

    client = _build_client(settings)
    if client.is_available():
        from app.ai.admission import BudgetedClient

        # Admission owns retries so each HTTP attempt consumes shared budget.
        account = settings.nvidia_api_key
        client = BudgetedClient(client, settings, settings.ai_provider + ":" + account)

    with _client_cache_lock:
        _client_cache[key] = client
    return client


def _build_client(settings: Settings) -> AIClient:
    """Internal factory — called once per unique Settings instance."""
    fallback_model = settings.nvidia_model
    if settings.ai_disable_network:
        LOGGER.info("AI disabled by AI_DISABLE_NETWORK=1; using NullClient")
        return NullClient(model=fallback_model)

    provider = (settings.ai_provider or "").strip().lower()
    if provider in ("", "none"):
        return NullClient(model=fallback_model)

    if provider == "nvidia":
        if not settings.nvidia_api_key:
            LOGGER.warning("AI_PROVIDER=nvidia but NVIDIA_API_KEY is empty; using NullClient")
            return NullClient(model=settings.nvidia_model)
        if settings.nvidia_model == "nvidia/nemotron-3.5-lightning-30b-a3b":
            from app.ai.nemotron_client import NemotronClient

            return NemotronClient(
                api_key=settings.nvidia_api_key, model=settings.nvidia_model,
                base_url=settings.nvidia_base_url, timeout_seconds=settings.ai_timeout_seconds,
                reasoning_budget=settings.nvidia_reasoning_budget,
                max_output_tokens=settings.ai_max_output_tokens,
            )
        return NvidiaClient(
            api_key=settings.nvidia_api_key,
            model=settings.nvidia_model,
            base_url=settings.nvidia_base_url,
            enable_thinking=settings.nvidia_enable_thinking,
            clear_thinking=settings.nvidia_clear_thinking,
            timeout_seconds=settings.ai_timeout_seconds,
            max_retries=0,
        )

    LOGGER.warning("Unknown AI_PROVIDER=%r; using NullClient", provider)
    return NullClient(model=fallback_model)
