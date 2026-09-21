"""Tests for app.ai.cache."""

from __future__ import annotations

import asyncio

import pytest

from app.ai.cache import AsyncTTLCache, make_cache_key


@pytest.mark.unit
def test_make_cache_key_is_deterministic() -> None:
    a = make_cache_key("nvidia-model", "hello", None, 0.1)
    b = make_cache_key("nvidia-model", "hello", None, 0.1)
    assert a == b
    assert len(a) == 64


@pytest.mark.unit
@pytest.mark.parametrize(
    "left, right",
    [
        (("nvidia-model-a", "p", None, 0.1), ("nvidia-model-b", "p", None, 0.1)),
        (("m", "hello", None, 0.1), ("m", "hi", None, 0.1)),
        (("m", "p", "sys-a", 0.1), ("m", "p", "sys-b", 0.1)),
        (("m", "p", None, 0.1), ("m", "p", None, 0.2)),
    ],
)
def test_make_cache_key_changes_with_inputs(
    left: tuple[str, str, str | None, float],
    right: tuple[str, str, str | None, float],
) -> None:
    assert make_cache_key(*left) != make_cache_key(*right)


@pytest.mark.unit
def test_make_cache_key_treats_none_and_empty_system_equally() -> None:
    a = make_cache_key("m", "p", None, 0.1)
    b = make_cache_key("m", "p", "", 0.1)
    assert a == b


@pytest.mark.unit
def test_async_ttl_cache_rejects_invalid_args() -> None:
    with pytest.raises(ValueError):
        AsyncTTLCache(maxsize=0, ttl_seconds=1.0)
    with pytest.raises(ValueError):
        AsyncTTLCache(maxsize=1, ttl_seconds=0)


@pytest.mark.unit
def test_async_ttl_cache_get_set_roundtrip() -> None:
    cache: AsyncTTLCache[str] = AsyncTTLCache(maxsize=10, ttl_seconds=10.0)

    async def run() -> None:
        assert await cache.get("missing") is None
        await cache.set("k", "v")
        assert await cache.get("k") == "v"
        assert "k" in cache
        assert "missing" not in cache
        assert 123 not in cache  # type: ignore[operator]
        assert len(cache) == 1

    asyncio.run(run())


@pytest.mark.unit
def test_async_ttl_cache_ttl_expiry() -> None:
    cache: AsyncTTLCache[str] = AsyncTTLCache(maxsize=4, ttl_seconds=0.05)

    async def run() -> None:
        await cache.set("k", "v")
        assert await cache.get("k") == "v"
        await asyncio.sleep(0.1)
        assert await cache.get("k") is None

    asyncio.run(run())


@pytest.mark.unit
def test_async_ttl_cache_lru_eviction() -> None:
    cache: AsyncTTLCache[int] = AsyncTTLCache(maxsize=2, ttl_seconds=10.0)

    async def run() -> None:
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.set("c", 3)
        assert len(cache) == 2

    asyncio.run(run())


@pytest.mark.unit
def test_async_ttl_cache_clear() -> None:
    cache: AsyncTTLCache[str] = AsyncTTLCache(maxsize=4, ttl_seconds=10.0)

    async def run() -> None:
        await cache.set("a", "x")
        await cache.set("b", "y")
        cache.clear()
        assert len(cache) == 0
        assert await cache.get("a") is None

    asyncio.run(run())
