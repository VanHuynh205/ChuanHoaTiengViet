# -*- coding: utf-8 -*-
"""[DEBUG-a4f2] Probe: measure real NVIDIA latency for review_all chunks,
thinking ON vs OFF, with finish_reason/usage capture.

Runs the REAL SemanticVerifier (same prompt construction as production) on the
saved rule-based output, but with a raw client (no FallbackClient cap, no
budget) so we can see the primary model's true latency.

Usage:
  ..\\.venv\\Scripts\\python.exe .scratch/ai-semantic-fix/probe_latency.py
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
from app.ai.client import NvidiaClient  # noqa: E402
from app.ai.semantic_verifier import SemanticVerifier  # noqa: E402

TAG = "[DEBUG-a4f2]"


class ProbeClient(NvidiaClient):
    calls: list[dict] = []

    async def _post_once(self, url, headers, body):
        t0 = time.perf_counter()
        payload = await super()._post_once(url, headers, body)
        dt = time.perf_counter() - t0
        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        ProbeClient.calls.append({
            "latency_s": round(dt, 2),
            "max_tokens": body.get("max_tokens"),
            "thinking_flag": (body.get("chat_template_kwargs") or {}).get("enable_thinking",
                              "absent"),
            "finish_reason": choice.get("finish_reason"),
            "usage": payload.get("usage"),
            "content_head": str(message.get("content") or "")[:120],
            "reasoning_head": str(message.get("reasoning_content") or "")[:80],
        })
        return payload


def build_verifier(settings, thinking: bool) -> SemanticVerifier:
    client = ProbeClient(
        api_key=settings.nvidia_api_key,
        model=settings.nvidia_model,
        base_url=settings.nvidia_base_url,
        enable_thinking=thinking,
        clear_thinking=settings.nvidia_clear_thinking,
        timeout_seconds=settings.ai_timeout_seconds,
        max_retries=0,
    )
    return SemanticVerifier(
        ai_client=client,
        confidence_threshold=settings.semantic_verify_confidence_threshold,
        max_tokens=settings.semantic_verify_max_tokens,
        max_chunks=settings.semantic_verify_max_chunks,
        max_concurrency=settings.semantic_verify_max_concurrency,
        timeout_seconds=settings.ai_timeout_seconds,
        review_chunk_words=settings.semantic_review_chunk_words,
        max_output_tokens=settings.ai_max_output_tokens,
    )


async def scenario(name: str, text: str, source: str, thinking: bool) -> None:
    ProbeClient.calls.clear()
    verifier = build_verifier(get_settings(), thinking)
    started = time.perf_counter()
    result = await verifier.verify(
        text=text,
        diacritic_candidates=None,
        abbreviation_options=None,
        review_all=True,
        source_text=source,
    )
    wall = time.perf_counter() - started
    print(f"\n{TAG} === scenario {name} (thinking={thinking}) wall={wall:.1f}s")
    print(f"{TAG} status={result.status} reason={result.reason} "
          f"conf={result.confidence} chunks={result.verified_chunks}/{result.total_chunks}")
    for i, call in enumerate(ProbeClient.calls):
        print(f"{TAG} call[{i}]: {json.dumps(call, ensure_ascii=False)}")
    out = os.path.join(HERE, f"probe_{name}.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(result.verified_text)
    print(f"{TAG} verified -> {out}")


async def main() -> None:
    settings = get_settings()
    with open(os.path.join(HERE, "Test1.rulebased.txt"), encoding="utf-8") as f:
        rulebased = f.read()
    with open(os.path.join(HERE, "Test1.txt"), encoding="utf-8") as f:
        source = f.read()
    words = len(rulebased.split())
    print(f"{TAG} rulebased words={words} model={settings.nvidia_model}")

    await scenario("thinking_on", rulebased, source, thinking=True)
    await asyncio.sleep(2)
    await scenario("thinking_off", rulebased, source, thinking=False)


if __name__ == "__main__":
    asyncio.run(main())
