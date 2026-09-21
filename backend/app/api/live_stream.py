"""Deliver full, version-local snapshots as semantic chunks finish."""

from __future__ import annotations

import asyncio
import copy
import json

from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from app.ai.admission import ai_user_scope
from app.api.schemas import LiveNormalizeResponse
from app.normalizer.live_normalizer import _remap_expanded_abbreviation_spans


def stream_verification(service, baseline, original_text, word_map, user_id):
    baseline = copy.deepcopy(baseline)
    async def events():
        queue = asyncio.Queue(maxsize=2)
        latest = baseline.to_payload()

        async def progress(verification):
            if not await service.dictionary_is_current():
                return
            partial = copy.deepcopy(baseline)
            confidence = float(getattr(verification, "confidence", 0.0) or 0.0)
            # Streaming must obey the same safety boundary as the final
            # snapshot. A shape-valid, low-confidence full-text rewrite is not
            # allowed to replace the dataset baseline; the only low-confidence
            # exception is an abbreviation/teencode correction.
            allow_uncertain_abbreviation = bool(baseline.ambiguities) and bool(
                getattr(verification, "corrections", [])
            )
            if confidence >= service.settings.semantic_verify_confidence_threshold or allow_uncertain_abbreviation:
                partial.primary_output = verification.verified_text
            else:
                partial.semantic_status_reason = "low_confidence"
            partial.semantic_status = "partial"
            partial.semantic_status_reason = "chunk_scope_incomplete"
            partial.semantic_verified = False
            partial.semantic_verified_chunks = verification.verified_chunks
            partial.semantic_total_chunks = verification.total_chunks
            partial.semantic_confidence = verification.confidence
            partial.semantic_corrections = verification.corrections
            partial.expanded_abbreviations = _remap_expanded_abbreviation_spans(
                partial.expanded_abbreviations,
                partial.primary_output,
                corrections=verification.corrections,
                previous_output=baseline.primary_output,
            )
            for variant in partial.variants:
                if variant.is_primary:
                    variant.output = partial.primary_output
            await run_in_threadpool(service._populate_change_metadata, original_text, partial)
            await queue.put((partial.to_payload(), False))

        async def produce():
            try:
                with ai_user_scope(user_id):
                    final = await service.apply_semantic_verification(
                        copy.deepcopy(baseline),
                        original_text=original_text,
                        word_map=word_map,
                        on_progress=progress,
                    )
                await queue.put((final.to_payload(), True))
            except Exception:
                failed = dict(latest)
                failed.update(
                    semanticStatus="partial" if failed.get("semanticVerifiedChunks") else "error",
                    semanticStatusReason="provider_error",
                    semanticVerified=False,
                )
                await queue.put((failed, True))

        task = asyncio.create_task(produce())
        try:
            while True:
                latest, complete = await queue.get()
                if not await service.dictionary_is_current():
                    latest = baseline.to_payload()
                    latest.update(semanticStatus="not_checked", semanticStatusReason="dictionary_changed",
                                  semanticVerified=False)
                    complete = True
                validated = LiveNormalizeResponse.model_validate(latest).model_dump(by_alias=True)
                yield json.dumps(
                    {"result": validated, "complete": complete}, ensure_ascii=False
                ) + "\n"
                if complete:
                    break
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
