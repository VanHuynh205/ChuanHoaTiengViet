"""Text-only streaming transport for NVIDIA's chat endpoint."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx

from app.ai.client import (
    NVIDIA_BASE_URL,
    AIRequest,
    NvidiaClient,
    _parse_retry_after,
    _rate_limit_breaker,
    _usage_stats,
)
from app.ai.errors import AIAuthError, AINetworkError, AIParseError, AIRateLimitError, AITimeoutError


class NvidiaStreamingClient(NvidiaClient):
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: int = 60,
        max_retries: int = 0,
        base_url: str = NVIDIA_BASE_URL,
        reasoning_effort: str = "low",
        reasoning_token_reserve: int = 2048,
        max_output_tokens: int = 8192,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            api_key,
            model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            base_url=base_url,
            client=client,
        )
        if reasoning_effort not in {"low", "high", "max"}:
            raise ValueError("Unsupported NVIDIA reasoning effort")
        self._reasoning_effort = reasoning_effort
        self._reasoning_token_reserve = max(0, reasoning_token_reserve)
        self._max_output_tokens = max(1, max_output_tokens)

    def _build_body(self, request: AIRequest) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        return {
            "model": self.model,
            "messages": messages,
            "max_tokens": min(
                self._max_output_tokens, max(1, request.max_tokens) + self._reasoning_token_reserve
            ),
            "temperature": request.temperature,
            "seed": 0,
            "stream": True,
            "reasoning_effort": self._reasoning_effort,
        }

    async def _post_once(
        self,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
    ) -> dict[str, Any]:
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            async with client.stream(
                "POST", url, headers={**headers, "Accept": "text/event-stream"}, json=dict(body)
            ) as response:
                self._check_status(response)
                if "text/event-stream" not in response.headers.get("content-type", ""):
                    raise AIParseError("NVIDIA returned an unexpected response type")
                content: list[str] = []
                data: list[str] = []
                finish_reason = None
                usage: dict[str, Any] = {}
                received = 0

                def consume() -> bool:
                    nonlocal finish_reason, usage
                    value = "\n".join(data)
                    data.clear()
                    if value == "[DONE]":
                        return True
                    if not value:
                        return False
                    try:
                        payload = json.loads(value)
                        if not isinstance(payload, dict) or "error" in payload:
                            raise ValueError("Invalid event")
                        if isinstance(payload.get("usage"), dict):
                            usage = payload["usage"]
                        for choice in payload.get("choices", []):
                            if choice.get("index", 0) != 0:
                                continue
                            delta = choice.get("delta") or {}
                            part = delta.get("content")
                            if part is not None:
                                if not isinstance(part, str):
                                    raise ValueError("Invalid content")
                                content.append(part)
                            if choice.get("finish_reason") is not None:
                                if not isinstance(choice["finish_reason"], str):
                                    raise ValueError("Invalid finish reason")
                                finish_reason = choice["finish_reason"]
                    except (ValueError, TypeError, AttributeError) as exc:
                        raise AIParseError("Malformed NVIDIA stream event") from exc
                    return False

                async for line in response.aiter_lines():
                    received += len(line)
                    if received > 2_000_000:
                        raise AIParseError("NVIDIA response exceeded size limit")
                    if not line:
                        if consume():
                            break
                    elif line.startswith("data:"):
                        data.append(line[5:].lstrip(" "))
                if data:
                    consume()
                if finish_reason != "stop":
                    reason = (
                        finish_reason
                        if finish_reason in {"length", "content_filter", "tool_calls"}
                        else "unfinished"
                    )
                    raise AIParseError(f"NVIDIA completion not accepted ({reason})")
                text = "".join(content)
                if not text.strip():
                    raise AIParseError("NVIDIA returned no final content")
                try:
                    tokens = int(usage.get("total_tokens", 0) or 0)
                except (ValueError, TypeError, OverflowError) as exc:
                    raise AIParseError("Invalid NVIDIA token usage") from exc
                return {
                    "choices": [{"message": {"content": text}}],
                    "usage": {"total_tokens": max(0, tokens)},
                }
        finally:
            if self._client is None:
                await client.aclose()

    @staticmethod
    def _check_status(response: httpx.Response) -> None:
        status = response.status_code
        if status in {401, 403}:
            raise AIAuthError(f"NVIDIA authentication rejected ({status})")
        if status == 429:
            _rate_limit_breaker.trip(_parse_retry_after(response))
            _usage_stats.record_rate_limit()
            raise AIRateLimitError("NVIDIA provider quota reached")
        if status == 202:
            # Preserve dataset output rather than treating an acknowledgement as text.
            raise AIParseError("NVIDIA request pending; no completed response available")
        if status == 504:
            # The upstream invocation may have started; resubmission can duplicate work.
            raise AITimeoutError("NVIDIA upstream invocation timed out (504)")
        if status >= 500:
            raise AINetworkError(f"NVIDIA service unavailable ({status})")
        if status != 200:
            raise AIParseError(f"NVIDIA request rejected ({status})")
