"""Compare targeted AI review with whole-text review on fixed, labeled fixtures.

Offline by default. --online explicitly uses the configured provider and shared
admission limits. Reads dataset files only; never writes candidate/user/history DBs.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import logging
from pathlib import Path
import re
import time
import httpx
from dataclasses import replace

from app.ai.client import AIResponse, build_default_client
from app.ai.semantic_verifier import SemanticVerifier
from app.ai.errors import AIParseError
from app.config import get_settings
from app.data_manager.pending_service import PendingAbbreviationService
from app.normalizer.diacritic_restorer import (
    SyncDiacriticRestorer,
    get_shared_word_map,
    get_shared_bigram_freq,
    get_shared_context_phrase_overrides,
)
from app.normalizer.live_normalizer import LiveNormalizerService

FIXTURES = Path(__file__).parents[1] / "tests" / "fixtures"


class ReadOnlyDataset(PendingAbbreviationService):
    def db_is_ready(self):
        return False

    def dictionary_revision(self):
        return 0

    def submit_pending_abbreviation(self, **kwargs):
        return {"abbr": kwargs["abbr"], "status": "EVALUATION_ONLY"}


class PacedClient:
    def __init__(self, client, interval=6.5):
        self.client, self.interval, self.next_start = client, interval, 0.0
        self.lock = asyncio.Lock()
        self.calls = 0
        self.tokens = 0
        self.errors = []
        self.responses = []

    def is_available(self):
        return self.client.is_available()

    async def complete(self, request):
        async with self.lock:
            await asyncio.sleep(max(0, self.next_start - time.monotonic()))
            self.next_start = time.monotonic() + self.interval
            self.calls += 1
        try:
            response = await self.client.complete(request)
        except Exception as exc:
            # Parser messages are generated locally and contain no request data.
            status = re.search(r"\b[45][0-9]{2}\b", str(exc))
            error = (
                str(exc)
                if isinstance(exc, AIParseError)
                else type(exc).__name__ + (" HTTP " + status[0] if status else "")
            )
            self.errors.append(error)
            print(json.dumps({"transport_error": error}), flush=True)
            raise
        self.tokens += response.tokens_used
        self.responses.append(
            {
                "text": response.text,
                "model": response.model,
                "max_tokens": request.max_tokens,
                "source_prompt": request.prompt,
            }
        )
        return response


class RecordedClient:
    """Replay exact captured requests to recheck local safeguards without inference."""

    def __init__(self, path):
        report = json.loads(path.read_text(encoding="utf-8"))
        self.responses = {
            response["source_prompt"]: response
            for case in report["cases"]
            for result in case["results"].values()
            for response in result.get("provider_responses", [])
        }

    def is_available(self):
        return True

    async def complete(self, request):
        response = self.responses[request.prompt]
        return AIResponse(response["text"], 0, 0, response["model"])


class TargetedVerifier(SemanticVerifier):
    async def verify(self, *args, **kwargs):
        kwargs.pop("review_all", None)
        kwargs.pop("source_text", None)
        return await super().verify(*args, **kwargs)


def word_errors(reference, output):
    expected, actual = re.findall(r"\w+", reference.casefold()), re.findall(
        r"\w+", output.casefold()
    )
    previous = list(range(len(actual) + 1))
    for i, word in enumerate(expected, 1):
        current = [i]
        for j, found in enumerate(actual, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (word != found)))
        previous = current
    return {
        "word_errors": previous[-1],
        "reference_words": len(expected),
        "wer": previous[-1] / max(1, len(expected)),
        "exact": reference == output,
    }


async def evaluate(args):
    settings = get_settings()
    if args.model:
        settings = replace(settings, nvidia_model=args.model)
    if args.timeout:
        settings = replace(settings, ai_timeout_seconds=args.timeout)
    data = ReadOnlyDataset(settings)
    words = get_shared_word_map(settings.data_dir)
    restorer = SyncDiacriticRestorer(
        word_map=words,
        detection_threshold=settings.diacritic_detection_threshold,
        min_text_length=settings.diacritic_min_text_length,
        bigram_freq=get_shared_bigram_freq(settings.data_dir),
        context_phrases=get_shared_context_phrase_overrides(settings.data_dir),
    )
    provider = build_default_client(settings) if args.online else None
    if args.replay:
        provider = RecordedClient(args.replay)
    if args.online and args.fallback:
        from app.ai.fallback_client import FallbackClient

        provider = FallbackClient(
            provider,
            build_default_client(
                replace(
                    settings,
                    nvidia_model=args.fallback,
                    ai_timeout_seconds=min(30, settings.ai_timeout_seconds),
                )
            ),
        )
    client = PacedClient(provider, interval=0 if args.replay else 6.5) if provider else None
    if client and not client.is_available():
        raise RuntimeError("Configured AI is unavailable")
    cases = json.loads((FIXTURES / "full_text_quality.json").read_text(encoding="utf-8"))
    if args.sample:
        cases.append(
            {
                "id": "user_sample",
                "group": "user_sample",
                "input": (FIXTURES / "full_text_user_sample.txt").read_text(encoding="utf-8"),
            }
        )
    if args.ids:
        cases = [case for case in cases if case["id"] in args.ids.split(",")]
    report = {
        "model": (
            settings.nvidia_model if settings.ai_provider == "nvidia" else settings.gemini_model
        ),
        "online": args.online,
        "cases": [],
        "notes": "Fixed small regression set; not a population accuracy estimate.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        item = dict(case, results={})
        service = LiveNormalizerService(settings, data, diacritic_restorer=restorer)
        baseline = await asyncio.to_thread(service.normalize_live, case["input"])
        modes = args.modes.split(",") if client else ["dataset"]
        for mode in modes:
            result = copy.deepcopy(baseline)
            started = time.monotonic()
            before_calls = client.calls if client else 0
            before_responses = len(client.responses) if client else 0
            if mode != "dataset":
                cls = TargetedVerifier if mode == "targeted" else SemanticVerifier
                service._semantic_verifier = cls(
                    client,
                    max_tokens=settings.semantic_verify_max_tokens,
                    max_chunks=settings.semantic_verify_max_chunks,
                    max_concurrency=settings.semantic_verify_max_concurrency,
                    timeout_seconds=settings.ai_timeout_seconds,
                    review_chunk_words=settings.semantic_review_chunk_words,
                    confidence_threshold=settings.semantic_verify_confidence_threshold,
                )
                if (
                    mode != "targeted"
                    or baseline.ambiguities
                    or (baseline.diacritic_applied and baseline.diacritic_changes)
                ):
                    result = await service.apply_semantic_verification(result, case["input"], words)
            entry = {
                "output": result.primary_output,
                "status": result.semantic_status,
                "reason": result.semantic_status_reason,
                "checked": result.semantic_verified_chunks,
                "total": result.semantic_total_chunks,
                "seconds": round(time.monotonic() - started, 3),
                "calls": (client.calls - before_calls) if client else 0,
            }
            if client:
                entry["provider_responses"] = client.responses[before_responses:]
            if "reference" in case:
                entry.update(word_errors(case["reference"], result.primary_output))
            item["results"][mode] = entry
            print(
                json.dumps(
                    {
                        "id": case["id"],
                        "mode": mode,
                        **{
                            k: v
                            for k, v in entry.items()
                            if k not in {"output", "provider_responses"}
                        },
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        report["cases"].append(item)
        report["calls"] = client.calls if client else 0
        report["tokens"] = client.tokens if client else 0
        report["transport_errors"] = client.errors if client else []
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--ids", default="")
    parser.add_argument("--modes", default="dataset,targeted,whole_text")
    parser.add_argument("--model", default="")
    parser.add_argument("--timeout", type=int, default=0)
    parser.add_argument("--fallback", default="")
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--catalog", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.catalog:
        settings = get_settings()
        response = httpx.get(
            settings.nvidia_base_url.rstrip("/") + "/models",
            headers={"Authorization": "Bearer " + settings.nvidia_api_key},
            timeout=20,
        )
        response.raise_for_status()
        ids = [item["id"] for item in response.json().get("data", [])]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(ids, indent=2), encoding="utf-8")
        print(
            json.dumps(
                [id for id in ids if any(key in id.lower() for key in ("qwen", "glm", "deepseek"))]
            )
        )
        return
    logging.basicConfig(level=logging.ERROR)
    report = asyncio.run(evaluate(args))
    if args.online and any(
        r["status"] in {"error", "quota", "unavailable"}
        for c in report["cases"]
        for r in c["results"].values()
    ):
        raise SystemExit(3)


if __name__ == "__main__":
    main()
