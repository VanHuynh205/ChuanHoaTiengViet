# -*- coding: utf-8 -*-
"""[DEBUG-a4f2] Repro harness: run the FULL live normalization + AI semantic
verification path against a long (~1000 word) text, exactly like the
/api/normalize/live endpoint does.

Usage:
  ..\\.venv\\Scripts\\python.exe .scratch/ai-semantic-fix/repro_verify.py Test1
  ..\\.venv\\Scripts\\python.exe .scratch/ai-semantic-fix/repro_verify.py Test2
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.config import get_settings  # noqa: E402
from app.bootstrap import build_pipeline  # noqa: E402
from app.normalizer.live_normalizer import LiveNormalizerService  # noqa: E402
from app.ai.services import get_semantic_verifier  # noqa: E402
from app.normalizer.diacritic_restorer import (  # noqa: E402
    SyncDiacriticRestorer,
    get_shared_bigram_freq,
    get_shared_context_phrase_overrides,
    get_shared_word_map,
)

TAG = "[DEBUG-a4f2]"


def patch_db_free() -> None:
    """[DEBUG-a4f2] Make the harness runnable without SQL Server.

    The sandboxed process cannot open SSPI connections to the local SQL
    instance. Force JSON-bootstrap-only live data and no-op pending writes so
    the AI-layer path under test is exercised unchanged.
    """
    from app.data_manager.pending_service import PendingAbbreviationService

    def _no_db(self):  # noqa: ANN001
        return False

    def _no_submit(self, abbr, **_kwargs):  # noqa: ANN001
        return {"abbr": abbr, "status": "IGNORED", "pending_id": None,
                "has_suggested": False}

    PendingAbbreviationService.db_is_ready = _no_db
    PendingAbbreviationService.submit_pending_abbreviation = _no_submit


def print_settings(settings) -> None:
    print(f"{TAG} ai_provider={settings.ai_provider}")
    print(f"{TAG} nvidia_model={settings.nvidia_model}")
    print(f"{TAG} semantic_fallback_model={settings.semantic_fallback_model}")
    print(f"{TAG} ai_timeout_seconds={settings.ai_timeout_seconds}")
    print(f"{TAG} ai_max_retries={settings.ai_max_retries}")
    print(f"{TAG} ai_max_output_tokens={settings.ai_max_output_tokens}")
    print(f"{TAG} semantic_verify_enabled={settings.semantic_verify_enabled}")
    print(f"{TAG} semantic_verify_confidence_threshold={settings.semantic_verify_confidence_threshold}")
    print(f"{TAG} semantic_review_chunk_words={settings.semantic_review_chunk_words}")
    print(f"{TAG} semantic_verify_max_chunks={settings.semantic_verify_max_chunks}")
    print(f"{TAG} semantic_verify_max_concurrency={settings.semantic_verify_max_concurrency}")
    print(f"{TAG} nvidia_enable_thinking={settings.nvidia_enable_thinking}")
    print(f"{TAG} nvidia_api_key_set={bool(settings.nvidia_api_key)}")


async def run(name: str) -> None:
    patch_db_free()
    settings = get_settings()
    print_settings(settings)

    with open(os.path.join(HERE, f"{name}.txt"), encoding="utf-8") as f:
        text = f.read()
    print(f"{TAG} input words={len(text.split())} chars={len(text)}")

    pipeline = build_pipeline(settings)
    word_map = get_shared_word_map(settings.data_dir)
    bigram_freq = get_shared_bigram_freq(settings.data_dir)
    context_phrases = get_shared_context_phrase_overrides(settings.data_dir)
    restorer = SyncDiacriticRestorer(
        word_map=word_map,
        detection_threshold=settings.diacritic_detection_threshold,
        min_text_length=settings.diacritic_min_text_length,
        bigram_freq=bigram_freq,
        context_phrases=context_phrases,
    ) if (settings.diacritic_auto_detect and word_map) else None
    verifier = get_semantic_verifier(settings)
    print(f"{TAG} verifier={'none' if verifier is None else type(verifier).__name__}")

    service = LiveNormalizerService(
        settings,
        pipeline.pending_service,
        diacritic_restorer=restorer,
        semantic_verifier=verifier,
    )

    t0 = time.perf_counter()
    result = await asyncio.to_thread(
        service.normalize_live, text, input_method="paste"
    )
    t1 = time.perf_counter()
    print(f"{TAG} rule-based done in {t1 - t0:.2f}s status={result.semantic_status}")
    rule_path = os.path.join(HERE, f"{name}.rulebased.txt")
    with open(rule_path, "w", encoding="utf-8") as f:
        f.write(result.primary_output)
    print(f"{TAG} rule-based output -> {rule_path}")

    t2 = time.perf_counter()
    result = await service.apply_semantic_verification(
        result, original_text=text, word_map=word_map
    )
    t3 = time.perf_counter()
    print(
        f"{TAG} semantic done in {t3 - t2:.2f}s status={result.semantic_status} "
        f"reason={result.semantic_status_reason} conf={result.semantic_confidence} "
        f"chunks={result.semantic_verified_chunks}/{result.semantic_total_chunks} "
        f"corrections={len(result.semantic_corrections)}"
    )
    final_path = os.path.join(HERE, f"{name}.final.txt")
    with open(final_path, "w", encoding="utf-8") as f:
        f.write(result.primary_output)
    print(f"{TAG} final output -> {final_path}")


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "Test1"
    asyncio.run(run(name))
