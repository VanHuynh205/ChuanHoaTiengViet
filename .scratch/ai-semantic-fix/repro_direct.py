# -*- coding: utf-8 -*-
"""[DEBUG-a4f2] Tight loop: call SemanticVerifier.verify(review_all=True)
directly on a long text, no rule-based pipeline, no DB.

Usage:
  ..\\.venv\\Scripts\\python.exe .scratch/ai-semantic-fix/repro_direct.py Test1
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.config import get_settings  # noqa: E402
from app.ai.client import build_default_client  # noqa: E402
from app.ai.services import get_semantic_verifier  # noqa: E402
from app.ai.admission import ai_user_scope  # noqa: E402

TAG = "[DEBUG-a4f2]"


def dump_raw_response(payload, path: str) -> None:
    """Write the raw provider JSON so we can inspect truncation/thinking."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except TypeError:
        pass


async def main(name: str) -> None:
    settings = get_settings()
    with open(os.path.join(HERE, f"{name}.txt"), encoding="utf-8") as f:
        text = f.read()
    # Simulate the rule-based output the verifier would receive in production:
    # for the AI-layer loop the raw text is a stand-in data payload.
    verifier = get_semantic_verifier(settings)
    if verifier is None:
        print(f"{TAG} verifier unavailable (settings) — abort")
        return
    print(f"{TAG} verifier={type(verifier).__name__}")
    print(f"{TAG} chunk_words={verifier._review_chunk_words} "
          f"max_chunks={verifier._max_chunks} conc={verifier._max_concurrency} "
          f"timeout={verifier._timeout_seconds} threshold={verifier._threshold}")

    started = time.perf_counter()
    with ai_user_scope("debug-a4f2"):
        result = await verifier.verify(
            text=text,
            diacritic_candidates=None,
            abbreviation_options=None,
            review_all=True,
            source_text=text,
        )
    elapsed = time.perf_counter() - started
    print(
        f"{TAG} status={result.status} reason={result.reason} "
        f"conf={result.confidence} chunks={result.verified_chunks}/{result.total_chunks} "
        f"skipped={result.skipped_chunks} latency_ms={result.latency_ms} wall={elapsed:.1f}s"
    )
    out = os.path.join(HERE, f"{name}.direct.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(result.verified_text)
    print(f"{TAG} verified text -> {out}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "Test1"))
