"""Context-aware disambiguation: diacritic refinement + abbreviation selection.

The ``ContextDisambiguator`` sends the normalised text and any ambiguous
abbreviations to the configured AI provider in a single call. The AI returns:
- ``refined_text``: text with corrected/completed diacritics
- ``disambiguations``: chosen meanings for each ambiguous abbreviation
- ``confidence``: overall confidence score

Results are cached (1-hour TTL) so repeated identical inputs skip the API.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.ai.budget import estimate_output_budget
from app.ai.cache import AsyncTTLCache, make_cache_key
from app.ai.client import AIClient, AIRequest
from app.ai.prompts import UNIFIED_CONTEXT_TEMPLATE, render

LOGGER = logging.getLogger(__name__)
DISAMBIGUATE_CACHE_TTL = 3_600
DISAMBIGUATE_CACHE_SIZE = 512


@dataclass(frozen=True)
class DisambiguationResult:
    abbr: str
    chosen: str
    confidence: float
    reason: str
    is_new: bool = False  # True when AI proposed a meaning outside the option list.


@dataclass(frozen=True)
class AmbiguityInput:
    abbr: str
    options: list[str]


@dataclass(frozen=True)
class ContextDisambiguationResult:
    refined_text: str
    disambiguations: list[DisambiguationResult]
    confidence: float
    from_cache: bool = False


class ContextDisambiguator:
    def __init__(self, ai_client: AIClient, max_output_tokens: int | None = None) -> None:
        self._ai_client = ai_client
        self._max_output_tokens = max_output_tokens
        self._cache: AsyncTTLCache[ContextDisambiguationResult] = AsyncTTLCache(
            maxsize=DISAMBIGUATE_CACHE_SIZE,
            ttl_seconds=DISAMBIGUATE_CACHE_TTL,
        )

    def is_available(self) -> bool:
        return self._ai_client.is_available()

    async def disambiguate(
        self,
        full_text: str,
        ambiguities: list[AmbiguityInput],
    ) -> ContextDisambiguationResult:
        cache_key = make_cache_key(
            "disambiguate",
            full_text,
            json.dumps([(a.abbr, a.options) for a in ambiguities], ensure_ascii=False),
            0.0,
        )
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return ContextDisambiguationResult(
                refined_text=cached.refined_text,
                disambiguations=cached.disambiguations,
                confidence=cached.confidence,
                from_cache=True,
            )

        ambiguity_lines: list[str] = []
        for amb in ambiguities:
            opts = ", ".join(f'"{o}"' for o in amb.options)
            ambiguity_lines.append(f'- "{amb.abbr}": [{opts}]')
        ambiguity_str = "\n".join(ambiguity_lines) if ambiguity_lines else "(không có)"

        prompt_text = render(
            UNIFIED_CONTEXT_TEMPLATE,
            {"full_text": full_text, "ambiguities": ambiguity_str},
        )

        request = AIRequest(
            prompt=prompt_text,
            max_tokens=estimate_output_budget(full_text, self._max_output_tokens)
            if self._max_output_tokens
            else estimate_output_budget(full_text),
            temperature=0.1,
            json_mode=True,
        )
        response = await self._ai_client.complete(request)
        result = _parse_disambiguation_response(response.text, full_text, ambiguities)
        await self._cache.set(cache_key, result)
        return result


def _parse_disambiguation_response(
    raw: str,
    original_text: str,
    ambiguities: list[AmbiguityInput],
) -> ContextDisambiguationResult:
    parsed = _try_parse_json(raw)
    if parsed is None:
        return ContextDisambiguationResult(
            refined_text=original_text,
            disambiguations=[],
            confidence=0.0,
        )

    refined = str(parsed.get("refined_text", original_text))
    confidence = _coerce_confidence(parsed.get("confidence", 0.5))
    raw_disambiguations = parsed.get("disambiguations", [])

    disambiguations: list[DisambiguationResult] = []
    if isinstance(raw_disambiguations, list):
        options_by_abbr = {a.abbr: {opt.strip().lower() for opt in a.options} for a in ambiguities}
        valid_abbrs = set(options_by_abbr.keys())
        for item in raw_disambiguations:
            if not isinstance(item, dict):
                continue
            abbr = str(item.get("abbr", ""))
            chosen = str(item.get("chosen", "")).strip()
            reason = str(item.get("reason", ""))
            # AI may explicitly mark a new meaning; also infer when the chosen
            # value is not present in the original option list.
            ai_marked_new = bool(item.get("is_new"))
            inferred_new = (
                abbr in options_by_abbr
                and bool(chosen)
                and chosen.lower() not in options_by_abbr[abbr]
            )
            is_new = ai_marked_new or inferred_new
            if abbr in valid_abbrs and chosen:
                disambiguations.append(
                    DisambiguationResult(
                        abbr=abbr,
                        chosen=chosen,
                        confidence=confidence,
                        reason=reason,
                        is_new=is_new,
                    )
                )

    return ContextDisambiguationResult(
        refined_text=refined,
        disambiguations=disambiguations,
        confidence=confidence,
    )


def _coerce_confidence(value: Any) -> float:
    """Never let a non-numeric ``confidence`` from the model raise.

    A model that answers ``"confidence": "cao"`` used to escape as a ValueError
    and reach the client as HTTP 500.
    """
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(max(confidence, 0.0), 1.0)


def _try_parse_json(raw: str) -> dict[str, Any] | None:
    """Parse a model reply, accepting only a JSON *object*.

    A top-level list (``["a", "b"]``) parses fine as JSON but then blows up on
    ``.get()``, so the isinstance check has to guard BOTH attempts.
    """
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
