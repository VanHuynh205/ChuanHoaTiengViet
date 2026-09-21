"""Try the selected quality model; fall back only on provider/transport failure."""

from __future__ import annotations

import asyncio
from dataclasses import replace

from app.ai.admission import ai_deadline_remaining, ai_deadline_scope
from app.ai.client import AIClient, AIRequest, AIResponse
from app.ai.errors import AINetworkError, AITimeoutError


class FallbackClient:
    def __init__(self, primary: AIClient, fallback: AIClient) -> None:
        self.primary, self.fallback = primary, fallback

    def is_available(self) -> bool:
        return self.primary.is_available() or self.fallback.is_available()

    async def complete(self, request: AIRequest) -> AIResponse:
        # A fallback is part of one logical verification, so it must share the
        # caller's deadline instead of starting a second full timeout window.
        timeout = getattr(getattr(self.primary, "_settings", None), "ai_timeout_seconds", None)
        if timeout is None:
            timeout = getattr(getattr(self.fallback, "_settings", None), "ai_timeout_seconds", None)
        if timeout is None:
            return await self._complete_without_deadline(request)
        try:
            # Seed the shared ContextVar before entering either child client.
            # Otherwise BudgetedClient resets its own deadline after the
            # primary attempt and the fallback silently receives a second full
            # timeout window. That produced two successful HTTP 200s followed
            # by a request-level "AI deadline exceeded".
            with ai_deadline_scope(float(timeout)):
                remaining = ai_deadline_remaining() or 0.0
                async with asyncio.timeout(remaining):
                    # Reserve a small tail for the fallback provider, but keep
                    # most of the shared deadline for the primary: measured on
                    # the NVIDIA free tier a 400-word review chunk needs
                    # roughly 20-50s on the primary model, and the old
                    # min(remaining / 2, 30) cap cancelled healthy primaries
                    # at 30s before rerunning the whole request on the
                    # fallback — doubling latency and ending in a guaranteed
                    # deadline failure on long text.
                    provider_timeout = remaining - min(20.0, remaining / 3.0)
                    if provider_timeout <= 0:
                        return await self._complete_fallback(request)
                    try:
                        async with asyncio.timeout(provider_timeout):
                            return await self._complete_without_deadline(
                                request, allow_fallback=False
                            )
                    except (TimeoutError, AITimeoutError, AINetworkError):
                        return await self._complete_fallback(request)
        except TimeoutError as exc:
            raise AITimeoutError("AI deadline exceeded") from exc

    async def _complete_without_deadline(self, request: AIRequest, allow_fallback: bool = True) -> AIResponse:
        try:
            return await self.primary.complete(request)
        except (AINetworkError, AITimeoutError):
            if not allow_fallback:
                raise
            # Malformed completed responses are not transport failures. Avoid
            # invoking the streaming fallback after an HTTP 200 with an invalid
            # payload; that path can hang until a second provider read timeout.
            response = await self.fallback.complete(request)
            return replace(response, fallback_used=True)

    async def _complete_fallback(self, request: AIRequest) -> AIResponse:
        response = await self.fallback.complete(request)
        return replace(response, fallback_used=True)
