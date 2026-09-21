"""TTL + LRU cache for AI responses.

The cache key is a SHA-256 of ``model + prompt + system + temperature`` so
identical inputs hit the same entry regardless of dict iteration order.
``cachetools.TTLCache`` handles expiry and LRU eviction; an ``asyncio.Lock``
keeps mutations safe under concurrent ``await`` points.

The interface deliberately stays small (``get`` / ``set`` / ``clear``) so a
later phase can swap the in-process backing for Redis without touching call
sites.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Generic, TypeVar

from cachetools import TTLCache

T = TypeVar("T")


def make_cache_key(
    model: str,
    prompt: str,
    system: str | None,
    temperature: float,
) -> str:
    """Derive a deterministic cache key for an AI request."""
    from app.ai.admission import user_cache_scope

    payload = f"{user_cache_scope()}\x00{model}\x00{prompt}\x00{system or ''}\x00{temperature:.6f}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AsyncTTLCache(Generic[T]):
    """Async-safe TTL+LRU cache wrapping ``cachetools.TTLCache``."""

    def __init__(self, maxsize: int, ttl_seconds: float) -> None:
        if maxsize <= 0:
            raise ValueError("maxsize must be positive")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._cache: TTLCache[str, T] = TTLCache(maxsize=maxsize, ttl=ttl_seconds)
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> T | None:
        async with self._lock:
            return self._cache.get(key)

    async def set(self, key: str, value: T) -> None:
        async with self._lock:
            self._cache[key] = value

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key in self._cache

    def clear(self) -> None:
        self._cache.clear()
