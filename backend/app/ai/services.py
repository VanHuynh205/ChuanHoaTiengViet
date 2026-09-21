"""Process-wide factories for the AI helper objects.

Both ``SemanticVerifier`` and ``ContextDisambiguator`` own a 1-hour TTL cache,
but the routes used to construct a fresh instance per request — so the cache was
discarded before it could ever be hit and every repeated input paid for another
provider call. These factories memoise one instance per ``Settings`` so the
caches actually live as long as the process.
"""

from __future__ import annotations

from threading import Lock
from typing import Optional
from dataclasses import replace

from app.ai.client import build_default_client
from app.ai.disambiguator import ContextDisambiguator
from app.config import Settings

_verifier_cache: dict[Settings, object] = {}
_disambiguator_cache: dict[Settings, ContextDisambiguator] = {}
_cache_lock = Lock()


def get_semantic_verifier(settings: Settings) -> Optional[object]:
    """Return the shared ``SemanticVerifier``, or ``None`` when AI is off."""
    if (
        not settings.semantic_verify_enabled
        or settings.ai_provider == "none"
        or settings.ai_disable_network
    ):
        return None

    with _cache_lock:
        cached = _verifier_cache.get(settings)
    if cached is not None:
        return cached

    ai_client = build_default_client(settings)
    if settings.ai_provider == "nvidia" and settings.semantic_fallback_model and settings.semantic_fallback_model != settings.nvidia_model:
        from app.ai.fallback_client import FallbackClient
        # The fallback shares the caller's single deadline (FallbackClient
        # seeds one ai_deadline_scope), so giving it the full window does not
        # extend the total wait; a shorter httpx window here just guaranteed
        # the fallback could never finish regenerating a long chunk.
        fallback_settings = replace(settings, nvidia_model=settings.semantic_fallback_model)
        ai_client = FallbackClient(ai_client, build_default_client(fallback_settings))
    if not ai_client.is_available():
        return None

    from app.ai.semantic_verifier import SemanticVerifier

    verifier = SemanticVerifier(
        ai_client=ai_client,
        confidence_threshold=settings.semantic_verify_confidence_threshold,
        max_tokens=settings.semantic_verify_max_tokens,
        max_chunks=settings.semantic_verify_max_chunks,
        max_concurrency=settings.semantic_verify_max_concurrency,
        timeout_seconds=settings.ai_timeout_seconds,
        review_chunk_words=settings.semantic_review_chunk_words,
        max_output_tokens=settings.ai_max_output_tokens,
    )
    with _cache_lock:
        _verifier_cache.setdefault(settings, verifier)
        return _verifier_cache[settings]


def get_disambiguator(settings: Settings) -> Optional[ContextDisambiguator]:
    """Return the shared ``ContextDisambiguator`` for these settings."""
    with _cache_lock:
        cached = _disambiguator_cache.get(settings)
    if cached is not None:
        return cached

    disambiguator = ContextDisambiguator(
        ai_client=build_default_client(settings),
        max_output_tokens=settings.ai_max_output_tokens,
    )
    with _cache_lock:
        _disambiguator_cache.setdefault(settings, disambiguator)
        return _disambiguator_cache[settings]


def reset_ai_service_cache() -> None:
    """Drop the memoised helpers — for tests that swap out settings."""
    with _cache_lock:
        _verifier_cache.clear()
        _disambiguator_cache.clear()
