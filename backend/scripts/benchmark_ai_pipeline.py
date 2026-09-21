"""Deterministic AI-pipeline benchmark; provider calls are replaced by a fake client."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.client import AIResponse
from app.ai.semantic_verifier import SemanticVerifier


class RecordingClient:
    def __init__(self) -> None:
        self.requests = []

    def is_available(self) -> bool:
        return True

    async def complete(self, request):
        self.requests.append(request)
        return AIResponse(
            json.dumps({"verified_text": "", "confidence": 0.0, "corrections": []}),
            0,
            0,
            "benchmark-fake",
        )


async def run(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    client = RecordingClient()
    verifier = SemanticVerifier(client, review_chunk_words=800, max_chunks=64, max_concurrency=2)
    started = time.perf_counter()
    result = await verifier.verify(text, review_all=True, source_text=text)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "file": path.name,
        "characters": len(text),
        "words": len(text.split()),
        "aiCalls": len(client.requests),
        "promptCharacters": sum(len(request.prompt) for request in client.requests),
        "maxPromptCharacters": max((len(request.prompt) for request in client.requests), default=0),
        "wallMs": round(elapsed_ms, 2),
        "status": result.status,
    }


async def main() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = [root / "tests" / "fixtures" / "full_text_user_sample.txt"]
    print(json.dumps([await run(path) for path in paths], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
