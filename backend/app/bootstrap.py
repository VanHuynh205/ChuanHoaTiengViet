"""Application bootstrap helpers.

Provides cached factories for the normalization pipeline and related services
so the CLI entrypoint (``app.main``) and the HTTP API (``app.api.routes``) can
share construction without one importing the other.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from app.config import Settings, get_settings
from app.data_manager.pending_service import PendingAbbreviationService
from app.normalizer.diacritic_restorer import (
    SyncDiacriticRestorer,
    get_shared_context_phrase_overrides,
    get_shared_bigram_freq,
    get_shared_word_map,
)
from app.normalizer.pipeline import VietnameseNormalizerPipeline


@lru_cache(maxsize=4)
def _build_pipeline_cached(settings: Settings) -> VietnameseNormalizerPipeline:
    pending_service = PendingAbbreviationService(settings)
    diacritic_restorer: Optional[SyncDiacriticRestorer] = None
    if settings.diacritic_auto_detect:
        word_map = get_shared_word_map(settings.data_dir)
        if word_map:
            bigram_freq = get_shared_bigram_freq(settings.data_dir)
            context_phrases = get_shared_context_phrase_overrides(settings.data_dir)
            diacritic_restorer = SyncDiacriticRestorer(
                word_map=word_map,
                detection_threshold=settings.diacritic_detection_threshold,
                min_text_length=settings.diacritic_min_text_length,
                bigram_freq=bigram_freq,
                context_phrases=context_phrases,
            )
    return VietnameseNormalizerPipeline(
        settings=settings,
        pending_service=pending_service,
        diacritic_restorer=diacritic_restorer,
    )


def build_pipeline(settings: Optional[Settings] = None) -> VietnameseNormalizerPipeline:
    """Return a process-wide cached normalization pipeline.

    The result is memoised per ``Settings`` instance — combined with the
    ``lru_cache`` on :func:`app.config.get_settings`, every request in a single
    worker reuses the same pipeline (and its underlying word map and DB session
    factory).
    """
    return _build_pipeline_cached(settings or get_settings())


def reset_pipeline_cache() -> None:
    """Clear the cached pipeline — for tests that mutate ``Settings``."""
    _build_pipeline_cached.cache_clear()
