from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Mapping, Sequence

from app.utils.text_utils import tokenize_for_scan


@dataclass(frozen=True)
class ContextualChoice:
    selected: str
    confidence: float
    reason: str


_SENTENCE_BOUNDARIES = {".", "!", "?", ";", "\u2026"}
_ROMANCE_CONTEXT = {
    "bo",
    "crush",
    "cu",
    "hen",
    "nguoi",
    "ny",
    "nyc",
    "tay",
    "yeu",
}
_BUSINESS_CONTEXT = {
    "an",
    "cong",
    "du",
    "hop",
    "khach",
    "lam",
    "luong",
    "nhan",
    "phong",
    "sep",
    "su",
    "ty",
    "van",
    "viec",
}
_RECENT_ACTION_CONTEXT = {"moi", "vua", "dang", "da"}


def choose_contextual_option(
    *,
    abbr: str,
    options: Sequence[str],
    tokens: Sequence[str],
    token_index: int,
    abbreviations: Mapping[str, str],
) -> ContextualChoice | None:
    """Choose an abbreviation meaning when nearby words make one option clear."""

    normalized_options = _dedupe_options(options)
    if len(normalized_options) < 2:
        return None

    left_context, right_context = _context_tokens(tokens, token_index, abbreviations)
    scored: list[tuple[int, int, str, str]] = []
    for index, option in enumerate(normalized_options):
        score, reason = _score_option(option, left_context, right_context)
        scored.append((score, -index, option, reason))

    scored.sort(reverse=True)
    best_score, _, best_option, reason = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0
    if best_score < 4 or best_score - second_score < 2:
        return None

    confidence = min(0.98, 0.70 + (best_score - second_score) * 0.03)
    return ContextualChoice(
        selected=best_option,
        confidence=confidence,
        reason=reason or f"{abbr} fits the local context",
    )


def _score_option(
    option: str, left_context: Sequence[str], right_context: Sequence[str]
) -> tuple[int, str]:
    option_key = _fold(" ".join(_word_tokens(option)))
    context = [*left_context, *right_context]
    score = 0
    reasons: list[str] = []

    if option_key == "chia tay":
        if _starts_with(right_context, ("nguoi", "yeu")) or _starts_with(right_context, ("ny",)):
            score += 9
            reasons.append("right context mentions a romantic partner")
        if left_context and left_context[-1] in _RECENT_ACTION_CONTEXT:
            score += 3
            reasons.append("left context is a recent-action marker")
        if any(token in _ROMANCE_CONTEXT for token in context):
            score += 2
        if any(token in _BUSINESS_CONTEXT for token in right_context[:3]):
            score -= 4

    if option_key == "cong ty":
        if any(token in _BUSINESS_CONTEXT for token in context):
            score += 5
            reasons.append("nearby words are work/business terms")
        if left_context and left_context[-1] in {"o", "tai", "vao", "den"}:
            score += 2
        if _starts_with(right_context, ("nguoi", "yeu")) or _starts_with(right_context, ("ny",)):
            score -= 7

    return score, "; ".join(reasons)


def _context_tokens(
    tokens: Sequence[str],
    token_index: int,
    abbreviations: Mapping[str, str],
    window: int = 5,
) -> tuple[list[str], list[str]]:
    left_start = max(0, token_index - window)
    for index in range(token_index - 1, left_start - 1, -1):
        if tokens[index] in _SENTENCE_BOUNDARIES:
            left_start = index + 1
            break

    right_end = min(len(tokens), token_index + window + 1)
    for index in range(token_index + 1, right_end):
        if tokens[index] in _SENTENCE_BOUNDARIES:
            right_end = index
            break

    left = _expand_context_tokens(tokens[left_start:token_index], abbreviations)
    right = _expand_context_tokens(tokens[token_index + 1 : right_end], abbreviations)
    return left, right


def _expand_context_tokens(tokens: Sequence[str], abbreviations: Mapping[str, str]) -> list[str]:
    expanded: list[str] = []
    for token in tokens:
        if not token.isalpha():
            continue
        lowered = token.lower()
        replacement = abbreviations.get(lowered, token)
        expanded.extend(_fold(word) for word in _word_tokens(replacement))
    return [token for token in expanded if token]


def _word_tokens(text: str) -> list[str]:
    return [token.lower() for token in tokenize_for_scan(text) if token.isalpha()]


def _starts_with(tokens: Sequence[str], prefix: Sequence[str]) -> bool:
    return len(tokens) >= len(prefix) and tuple(tokens[: len(prefix)]) == tuple(prefix)


def _dedupe_options(options: Sequence[str]) -> list[str]:
    result: list[str] = []
    for option in options:
        cleaned = str(option or "").strip()
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return stripped.replace("\u0111", "d")
