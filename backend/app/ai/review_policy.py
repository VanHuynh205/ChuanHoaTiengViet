"""Source alignment and conservative, local acceptance of whole-text AI edits.

No vocabulary fixes live here. A provider proposes contextual corrections; this
module prevents a fluent rewrite from deleting facts or modifying literals.
"""

from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
import re
import json
import unicodedata
from typing import TYPE_CHECKING

from app.utils.text_utils import protected_literal_spans

if TYPE_CHECKING:
    from app.ai.semantic_verifier import _TextChunk

REVIEW_POLICY_VERSION = "whole-text-v6-candidate-strip-and-partial-budget"
_TOKENS = re.compile(r"\w+|[^\w]", re.UNICODE)
_NEGATIONS = {"không", "chưa", "chẳng", "đừng", "chả"}
_MAX_CONTEXTUAL_EDITS = 24
_CONTEXTUAL_EDIT_RATIO = 0.12


def fold(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", value.casefold()) if unicodedata.category(c) != "Mn"
    ).replace("đ", "d")


def phonetic_fold(value: str) -> str:
    # Common Vietnamese onset confusions, not phrase-specific replacements.
    return re.sub(r"\b(?:ch|tr)", "tr", fold(value))


def _diacritic_count(value: str) -> int:
    """Count Vietnamese combining marks and precomposed accented letters."""
    decomposed = unicodedata.normalize("NFD", value)
    return sum(1 for char in decomposed if unicodedata.category(char) == "Mn")


def source_windows(source: str, normalized: str, chunks: list[_TextChunk]) -> list[str]:
    """Align raw-word offsets with normalized chunks, with context on both sides."""
    raw = list(re.finditer(r"\S+", source))
    if not raw:
        return [""] * len(chunks)
    output = list(re.finditer(r"\S+", normalized))
    opcodes = SequenceMatcher(
        None, [fold(w[0]) for w in raw], [fold(w[0]) for w in output], autojunk=False
    ).get_opcodes()

    def boundary(position: int, end: bool = False) -> int:
        for tag, a, b, c, d in opcodes:
            if c <= position < d or (end and c < position <= d):
                return a + position - c if tag == "equal" else (b if end else a)
        return len(raw)

    windows = []
    for chunk in chunks:
        begin = min(len(raw) - 1, boundary(chunk.start_word))
        finish = max(begin + 1, min(len(raw), boundary(chunk.end_word, True)))
        left, right = max(0, begin - 40), min(len(raw), finish + 40)
        windows.append(
            json.dumps(
                {
                    "original_segment": source[raw[begin].start() : raw[finish - 1].end()],
                    "previous_context": source[raw[left].start() : raw[begin].start()],
                    "following_context": source[raw[finish - 1].end() : raw[right - 1].end()],
                },
                ensure_ascii=False,
            )
        )
    return windows


def accept_edits(
    source: str,
    proposed: str,
    *,
    confidence: float,
    threshold: float,
    abbreviations: dict[str, list[str]] | None = None,
    diacritic_candidates: dict[str, list[str]] | None = None,
    original_segment: str = "",
) -> tuple[str, list[tuple[str, str]], int]:
    """Accept plausible word corrections independently, keeping layout verbatim.

    Uncertain teencode may expand; its presence never permits uncertain edits to
    the rest of the paragraph. Inserted/deleted facts and synonyms are excluded.
    """
    a, b = list(_TOKENS.finditer(source)), list(_TOKENS.finditer(proposed))
    protected = protected_literal_spans(source)
    keys = {key.casefold() for key in abbreviations or {}}
    offered_meanings = {
        str(key).casefold(): {str(option).strip().casefold() for option in options or []}
        for key, options in (abbreviations or {}).items()
    }
    recoverable = expansion_spans(original_segment, source)
    parts, changes, rejected = [], [], 0
    contextual_edits = 0
    source_word_count = max(1, len(re.findall(r"\w+", source, re.UNICODE)))
    edit_budget = min(_MAX_CONTEXTUAL_EDITS, max(4, int(source_word_count * _CONTEXTUAL_EDIT_RATIO)))
    allowed_diacritics = {
        fold(str(key)): {str(option).casefold() for option in options}
        for key, options in (diacritic_candidates or {}).items()
    }
    for tag, i, j, k, output_end in SequenceMatcher(
        None, [m[0] for m in a], [m[0] for m in b], autojunk=False
    ).get_opcodes():
        before = "".join(m[0] for m in a[i:j])
        after = "".join(m[0] for m in b[k:output_end])
        if tag == "equal":
            parts.append(before)
            continue
        start = a[i].start() if i < len(a) else len(source)
        end = a[j - 1].end() if j > i else start
        old_words, new_words = re.findall(r"\w+", before), re.findall(r"\w+", after)
        is_abbreviation = len(old_words) == 1 and old_words[0].casefold() in keys
        repairs_expansion = confidence >= threshold and any(
            x <= start and end <= y for x, y in recoverable
        )
        safe = bool(old_words and new_words)
        safe = safe and not any(x < end and y > start for x, y in protected)
        safe = safe and not any(
            c.isdigit() or unicodedata.category(c)[0] in {"P", "S"} or c in "\r\n\t"
            for c in before + after
        )
        safe = safe and confidence > 0 and (confidence >= threshold or is_abbreviation)
        if not is_abbreviation and not repairs_expansion:
            safe = safe and len(old_words) == len(new_words)
            safe = safe and (
                SequenceMatcher(None, fold(before), fold(after), autojunk=False).ratio() >= 0.6
                or phonetic_fold(before) == phonetic_fold(after)
            )
            # AI verification may restore accents, but it must never degrade
            # an already normalized dataset result by stripping Vietnamese
            # diacritics from an otherwise equivalent word. Exception: when
            # the bare form is one of the deterministic pass's own declared
            # candidates, the restorer may itself have added a WRONG tone
            # ("nghe" -> "nghề", "khan" -> "khăn"), and choosing another
            # declared candidate is the intended repair, not a degradation.
            # Only reject a pure accent-stripping rewrite. A real spelling
            # correction can legitimately change the base letters as well,
            # such as ``chá`` -> ``tra``.
            same_base_word = fold(before) == fold(after)
            strip_to_declared_candidate = bool(allowed_diacritics) and (
                fold(before) == fold(after)
                and after.strip().casefold()
                in allowed_diacritics.get(fold(before.strip()), frozenset())
            )
            safe = safe and (
                not same_base_word
                or _diacritic_count(after) >= _diacritic_count(before)
                or strip_to_declared_candidate
            )
        else:
            safe = safe and len(new_words) <= 8
            if is_abbreviation and confidence < threshold:
                # Below the confidence threshold the model may only apply one
                # of the meanings the dataset itself offered — never an
                # invented substitute for an ambiguous abbreviation.
                safe = safe and after.strip().casefold() in offered_meanings.get(
                    old_words[0].casefold(), set()
                )
        old_negation = Counter(w.casefold() for w in old_words if w.casefold() in _NEGATIONS)
        new_negation = Counter(w.casefold() for w in new_words if w.casefold() in _NEGATIONS)
        safe = safe and all(new_negation[word] >= count for word, count in old_negation.items())
        if safe and allowed_diacritics and fold(before) == fold(after) and before.casefold() != after.casefold():
            # Do not let a full-text model invent a different accent choice at
            # a position the deterministic diacritic pass already DECIDED: the
            # result must be one of that position's candidates. Tokens the pass
            # never surfaced (missing from the map entirely) fall through to
            # the generic similarity rules above — otherwise the model could
            # never repair the restorer's known blind spots ("met" → "mệt").
            source_key = fold(before.strip())
            licensed_candidates = allowed_diacritics.get(source_key)
            if licensed_candidates is not None:
                safe = any(
                    after.strip().casefold() == candidate
                    for candidate in licensed_candidates
                )
        # Explicit internal capitalization signals a name/product. Sentence
        # casing is handled by the normalizer, not by rewriting proper names.
        sentence_start = not source[:start].strip() or source[:start].rstrip()[-1:] in {
            ".",
            "!",
            "?",
            "…",
        }
        if not sentence_start and any(w[:1].isupper() for w in old_words):
            safe = safe and before.casefold() == after.casefold()
        if safe:
            # Expansion repairs consume the same budget as contextual edits:
            # rewriting every dataset expansion in a chunk is a wholesale
            # rewrite, not a correction.
            is_contextual_edit = (
                not is_abbreviation
                and fold(before) != fold(after)
            )
            if is_contextual_edit:
                contextual_edits += max(1, len(old_words), len(new_words))
            if is_contextual_edit and contextual_edits > edit_budget:
                # A sentence-level model can return a fluent rewrite that
                # is unrelated to normalization. Previously the whole chunk
                # was reverted, which threw away every good fix whenever a
                # messy baseline (dense unaccented chat text) blew the
                # budget. Keep the edits that fit the budget, in text
                # order, and serve the baseline for the overflow.
                rejected += 1
                parts.append(before)
            else:
                parts.append(after)
                changes.append((before, after))
        else:
            parts.append(before)
            rejected += 1
    return "".join(parts), changes, rejected


def expansion_spans(original: str, normalized: str) -> list[tuple[int, int]]:
    """Locate a short source token expanded to a phrase by the dataset.

    A wrong dataset expansion must not become immutable merely because its new
    words differ from the correct meaning. This grants only local, confident repairs.
    """
    a, b = list(re.finditer(r"\w+", original)), list(re.finditer(r"\w+", normalized))
    spans = []
    for tag, i, j, k, end in SequenceMatcher(
        None, [fold(m[0]) for m in a], [fold(m[0]) for m in b], autojunk=False
    ).get_opcodes():
        if tag == "replace" and j - i == 1 and 1 < end - k <= 8 and len(a[i][0]) <= 6:
            spans.append((b[k].start(), b[end - 1].end()))
    return spans
