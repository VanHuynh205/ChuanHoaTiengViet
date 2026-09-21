from __future__ import annotations

import bisect
import itertools
import copy
import asyncio
import json
import logging
import re
import threading
import time
import unicodedata
from difflib import SequenceMatcher
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from collections.abc import Callable
from typing import Dict, List, Literal, Optional

from app.ai.errors import AIError, AIRateLimitError
from app.config import Settings
from app.data_manager.pending_service import PendingAbbreviationService
from app.normalizer.abbreviation import expand_abbreviation
from app.normalizer.contextual_abbreviation import choose_contextual_option
from app.normalizer.diacritic_restorer import (
    SyncDiacriticRestorer,
    collect_ambiguous_diacritics,
)
from app.normalizer.emoji_remover import remove_emoji_and_emoticons
from app.normalizer.elongation import normalize_elongated_word
from app.normalizer.incremental_text import split_for_incremental_normalization
from app.normalizer.phrase_index import PhraseIndex, entries_from_phrase_dict
from app.normalizer.phrase_normalizer import PhraseMatch
from app.normalizer.pipeline import VietnameseNormalizerPipeline
from app.normalizer.spelling import apply_known_spelling
from app.normalizer.punctuation import append_question_mark, preserves_punctuation, restore_terminal_punctuation
from app.normalizer.unicode_normalizer import normalize_unicode
from app.utils.text_utils import (
    TokenLayout,
    capture_token_layout,
    capitalize_sentence_starts,
    join_scan_tokens,
    preserve_separator,
    tokenize_for_scan,
)


@dataclass
class _PendingBudget:
    """Moderation-write budget shared by every segment of ONE request."""

    remaining: int
    submitted_keys: set = field(default_factory=set)

    def consume(self, count: int = 1) -> bool:
        """Reserve ``count`` writes; ``False`` when the budget is exhausted."""
        if self.remaining < count:
            self.remaining = 0
            return False
        self.remaining -= count
        return True


@dataclass
class VariantResolution:
    ambiguity_id: str
    meaning: str


@dataclass
class LiveVariant:
    id: str
    output: str
    resolutions: List[VariantResolution] = field(default_factory=list)
    is_primary: bool = False


@dataclass
class LiveAmbiguity:
    id: str
    abbr: str
    token_index: int
    options: List[str]
    selected: str


@dataclass
class LiveNormalizationResult:
    primary_output: str
    variants: List[LiveVariant]
    ambiguities: List[LiveAmbiguity]
    pending_submissions: List[Dict[str, object]]
    warnings: List[str]
    error_types: List[str]
    latency_ms: float
    phrase_matches: List[PhraseMatch] = field(default_factory=list)
    diacritic_applied: bool = False
    diacritic_changes: List[tuple] = field(default_factory=list)
    semantic_verified: bool = False
    semantic_corrections: List[tuple] = field(default_factory=list)
    semantic_confidence: float = 0.0
    semantic_status: Literal[
        "not_needed", "not_checked", "verified", "uncertain", "partial", "unavailable", "quota", "error"
    ] = "not_needed"
    semantic_status_reason: str | None = None
    semantic_verified_chunks: int = 0
    semantic_total_chunks: int = 0
    semantic_from_cache: bool = False
    expanded_abbreviations: List[Dict[str, object]] = field(default_factory=list)
    changes: List[Dict[str, object]] = field(default_factory=list)

    def to_payload(self) -> dict:
        return {
            "primaryOutput": self.primary_output,
            "variants": [
                {
                    "id": variant.id,
                    "output": variant.output,
                    "resolutions": [asdict(resolution) for resolution in variant.resolutions],
                    "isPrimary": variant.is_primary,
                }
                for variant in self.variants
            ],
            "ambiguities": [asdict(ambiguity) for ambiguity in self.ambiguities],
            "pendingSubmissions": self.pending_submissions,
            "warnings": self.warnings,
            "errorTypes": self.error_types,
            "latencyMs": self.latency_ms,
            "phraseMatches": [
                {
                    "start": match.start_token,
                    "end": match.end_token,
                    "matched": match.matched_phrase,
                    "expanded": match.expanded,
                    "confidence": match.confidence,
                    "source": match.source,
                }
                for match in self.phrase_matches
            ],
            "diacriticApplied": self.diacritic_applied,
            "diacriticChanges": [list(pair) for pair in self.diacritic_changes],
            "semanticVerified": self.semantic_verified,
            "semanticCorrections": [list(pair) for pair in self.semantic_corrections],
            "semanticConfidence": self.semantic_confidence,
            "semanticStatus": self.semantic_status,
            "semanticStatusReason": self.semantic_status_reason,
            "semanticVerifiedChunks": self.semantic_verified_chunks,
            "semanticTotalChunks": self.semantic_total_chunks,
            "semanticFromCache": self.semantic_from_cache,
            "expandedAbbreviations": self.expanded_abbreviations,
            "changes": self.changes,
        }


def _strip_diacritics(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    ).lower()


def _fold_text_for_span_match(text: str) -> str:
    folded = _strip_diacritics(text).replace("đ", "d")
    return folded


def _folded_text_with_index_map(text: str) -> tuple[str, list[int]]:
    folded_chars: list[str] = []
    index_map: list[int] = []
    for index, char in enumerate(text):
        for folded_char in _fold_text_for_span_match(char):
            folded_chars.append(folded_char)
            index_map.append(index)
    return "".join(folded_chars), index_map


def _same_span_text(left: str, right: str) -> bool:
    return _fold_text_for_span_match(left) == _fold_text_for_span_match(right)


def _is_span_boundary(text: str, start: int, end: int) -> bool:
    return (
        (start <= 0 or not text[start - 1].isalnum())
        and (end >= len(text) or not text[end].isalnum())
    )


def _find_folded_token(
    text: str,
    needle: str,
    start: int = 0,
    folded: tuple[str, list[int]] | None = None,
) -> int | None:
    # ``folded`` lets callers that search the same text repeatedly (one span at
    # a time) fold it once instead of once per span.
    folded_text, index_map = folded if folded is not None else _folded_text_with_index_map(text)
    folded_needle = _fold_text_for_span_match(needle)
    if not folded_needle:
        return None
    # Equivalent to len(_fold_text_for_span_match(text[:start])): index_map is
    # non-decreasing and holds the source index of every folded character, so
    # the folded offset of source position ``start`` is the number of entries
    # below ``start``. bisect avoids re-folding the whole prefix per call.
    folded_start = bisect.bisect_left(index_map, start)
    found = folded_text.find(folded_needle, folded_start)
    while found >= 0:
        end = found + len(folded_needle)
        source_start = index_map[found]
        source_end = index_map[end - 1] + 1
        if _is_span_boundary(text, source_start, source_end):
            return source_start
        found = folded_text.find(folded_needle, found + 1)
    return None


def _overlaps_any(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    for range_start, range_end in ranges:
        if start == end:
            if range_start <= start < range_end:
                return True
        elif start < range_end and end > range_start:
            return True
    return False


def _classify_change(original: str, output: str) -> list[str]:
    kinds: list[str] = []
    if original and not output:
        kinds.append("deletion")
    elif original and output and output.lower() in original.lower() and len(original) > len(output):
        kinds.append("deletion")
    if original != output and original.lower() == output.lower():
        kinds.append("case")
    elif original and output and _strip_diacritics(original) == _strip_diacritics(output):
        kinds.append("diacritic")
        if original.lower() != output.lower():
            kinds.append("case")
    compact_original = "".join(original.split())
    compact_output = "".join(output.split())
    if original != output and compact_original == compact_output:
        kinds.append("whitespace")
    if not kinds:
        kinds.append("spelling")
    return kinds


def _apply_known_spelling(text: str, data_dir: object) -> str:
    """Apply only versioned, exact typo phrases outside protected literals."""
    return apply_known_spelling(text, str(data_dir))[0]


def _append_conservative_punctuation(text: str) -> str:
    """Add a question mark only for an unambiguous interrogative opening."""
    return append_question_mark(text)[0]


def _expand_word_change_bounds(
    original: str,
    output: str,
    source_start: int,
    source_end: int,
    output_start: int,
    output_end: int,
) -> tuple[int, int, int, int]:
    while (
        source_start > 0
        and output_start > 0
        and original[source_start - 1].isalnum()
        and output[output_start - 1].isalnum()
    ):
        source_start -= 1
        output_start -= 1
    while (
        source_end < len(original)
        and output_end < len(output)
        and original[source_end].isalnum()
        and output[output_end].isalnum()
    ):
        source_end += 1
        output_end += 1
    return source_start, source_end, output_start, output_end


def _word_change_ranges(original: str, output: str) -> list[tuple[int, int, int, int]]:
    """Split an AI replacement into word-sized ranges for comparison markup."""
    source_words = list(re.finditer(r"\w+", original, re.UNICODE))
    output_words = list(re.finditer(r"\w+", output, re.UNICODE))
    ranges: list[tuple[int, int, int, int]] = []
    for tag, source_i, source_j, output_i, output_j in SequenceMatcher(
        None,
        [match.group(0).casefold() for match in source_words],
        [match.group(0).casefold() for match in output_words],
        autojunk=False,
    ).get_opcodes():
        if tag == "equal":
            continue
        source_slice = source_words[source_i:source_j]
        output_slice = output_words[output_i:output_j]
        count = max(len(source_slice), len(output_slice))
        for offset in range(count):
            source_match = source_slice[offset] if offset < len(source_slice) else None
            output_match = output_slice[offset] if offset < len(output_slice) else None
            source_start = source_match.start() if source_match else (
                source_slice[-1].end() if source_slice else 0
            )
            source_end = source_match.end() if source_match else source_start
            output_start = output_match.start() if output_match else (
                output_slice[-1].end() if output_slice else 0
            )
            output_end = output_match.end() if output_match else output_start
            ranges.append((source_start, source_end, output_start, output_end))
    return ranges


def _allows_folded_span_fallback(needle: str) -> bool:
    folded = _fold_text_for_span_match(needle)
    return " " in folded or len(folded) >= 4


def _is_true_abbreviation(abbr: str, expanded: str) -> bool:
    """Return True only if the expansion changes more than just diacritics."""
    return _strip_diacritics(abbr) != _strip_diacritics(expanded)


def _pending_submission_rank(submission: Dict[str, object]) -> int:
    if submission.get("needs_user_meaning"):
        return 3
    if submission.get("can_add_more_meanings"):
        return 2
    if submission.get("pending_id"):
        return 1
    return 0


def _dedupe_pending_submissions(
    submissions: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    deduped: List[Dict[str, object]] = []
    index_by_key: dict[str, int] = {}

    for submission in submissions:
        abbr = str(submission.get("abbr") or "").strip().lower()
        if abbr:
            key = f"abbr:{abbr}"
        else:
            pending_id = str(submission.get("pending_id") or "").strip()
            status = str(submission.get("status") or "").strip()
            key = f"pending:{pending_id}:{status}:{len(deduped)}"

        existing_index = index_by_key.get(key)
        if existing_index is None:
            index_by_key[key] = len(deduped)
            deduped.append(submission)
            continue

        existing = deduped[existing_index]
        if _pending_submission_rank(submission) > _pending_submission_rank(existing):
            deduped[existing_index] = submission

    return deduped


def _find_unused_span(
    *,
    output: str,
    folded_output: str,
    output_index_map: list[int],
    needle: str,
    used_ranges: list[tuple[int, int]],
) -> tuple[int, int] | None:
    output_lower = output.lower()
    needle_lower = needle.lower()
    search_from = 0
    while search_from < len(output_lower):
        start = output_lower.find(needle_lower, search_from)
        if start == -1:
            break

        end = start + len(needle)
        if (
            _is_span_boundary(output, start, end)
            and not any(start < used_end and end > used_start for used_start, used_end in used_ranges)
        ):
            return start, end

        search_from = start + 1

    if not _allows_folded_span_fallback(needle):
        return None

    folded_needle = _fold_text_for_span_match(needle)
    if not folded_needle:
        return None

    search_from = 0
    while search_from < len(folded_output):
        folded_start = folded_output.find(folded_needle, search_from)
        if folded_start == -1:
            return None

        folded_end = folded_start + len(folded_needle)
        start = output_index_map[folded_start]
        end = output_index_map[folded_end - 1] + 1
        if (
            _is_span_boundary(output, start, end)
            and not any(start < used_end and end > used_start for used_start, used_end in used_ranges)
        ):
            return start, end

        search_from = folded_start + 1

    return None


def _remap_expanded_abbreviation_spans(
    spans: list[Dict[str, object]],
    output: str,
    corrections: list[tuple] | None = None,
    previous_output: str | None = None,
) -> list[Dict[str, object]]:
    folded_output, output_index_map = _folded_text_with_index_map(output)
    if not folded_output or not output_index_map:
        return []

    used_ranges: list[tuple[int, int]] = []
    remapped: list[Dict[str, object]] = []
    alignment = SequenceMatcher(None, previous_output, output, autojunk=False).get_opcodes() if previous_output is not None else []

    def project(position: int, right: bool = False) -> int | None:
        for tag, a, b, c, d in alignment:
            if a <= position < b or (right and a < position <= b):
                return c + position - a if tag == "equal" else (d if right else c)
        return None

    for span in spans:
        abbr = str(span.get("abbr") or "").strip()
        expanded = str(span.get("expanded") or "").strip()
        if not abbr or not expanded:
            continue

        candidates = [expanded]
        for before, after in corrections or []:
            before_text = str(before or "").strip()
            after_text = str(after or "").strip()
            if before_text and after_text and _same_span_text(before_text, expanded):
                candidates.append(after_text)

        match: tuple[int, int] | None = None
        start = span.get("start")
        end = span.get("end")
        if previous_output is not None and isinstance(start, int) and isinstance(end, int):
            mapped_start, mapped_end = project(start), project(end, True)
            if mapped_start is not None and mapped_end is not None and mapped_start < mapped_end:
                candidate = output[mapped_start:mapped_end]
                if candidate.casefold() == abbr.casefold():
                    continue
                candidates.insert(0, candidate)
                match = (mapped_start, mapped_end)
        if match is None and isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(output):
            current_text = output[start:end]
            if any(_same_span_text(current_text, candidate) for candidate in candidates):
                match = (start, end)

        if match is None:
            for candidate in candidates:
                match = _find_unused_span(
                    output=output,
                    folded_output=folded_output,
                    output_index_map=output_index_map,
                    needle=candidate,
                    used_ranges=used_ranges,
                )
                if match is not None:
                    break

        if match is None:
            continue

        start, end = match
        used_ranges.append((start, end))
        next_span = dict(span)
        next_span["start"] = start
        next_span["end"] = end
        next_span["expanded"] = output[start:end]
        next_span["source"] = str(next_span.get("source") or "token")
        remapped.append(next_span)

    return remapped


class LiveNormalizerService:
    _segment_cache: "OrderedDict[str, LiveNormalizationResult]" = OrderedDict()
    _segment_cache_lock = threading.Lock()

    def __init__(
        self,
        settings: Settings,
        pending_service: PendingAbbreviationService,
        diacritic_restorer: Optional[SyncDiacriticRestorer] = None,
        semantic_verifier: object | None = None,
        usage_stats_repository: object | None = None,
        request_meanings: object | None = None,
    ) -> None:
        self.settings = settings
        self.pending_service = pending_service
        self._diacritic_restorer = diacritic_restorer
        self._semantic_verifier = semantic_verifier
        self._usage_stats_repository = usage_stats_repository
        self._request_meanings = request_meanings
        self._pipeline = VietnameseNormalizerPipeline(
            settings=settings,
            pending_service=pending_service,
            diacritic_restorer=diacritic_restorer,
        )

    def normalize_live(
        self,
        text: str,
        submitted_by: Optional[str] = None,
        user_id: Optional[str] = None,
        domain: str = "general",
        resolution_overrides: Optional[Dict[str, str]] = None,
        input_method: str = "paste",
    ) -> LiveNormalizationResult:
        self._request_dictionary_revision = self._live_data_generation()
        original_text = text
        text, self._spelling_edits = apply_known_spelling(text, str(self.settings.data_dir))
        self._spelling_output = text
        if self._should_use_incremental_segments(text, resolution_overrides):
            result = self._normalize_incremental_segments(
                text=text,
                submitted_by=submitted_by,
                user_id=user_id,
                domain=domain,
                input_method=input_method,
            )
        else:
            result = self._normalize_live_uncached(
                text=text,
                submitted_by=submitted_by,
                user_id=user_id,
                domain=domain,
                resolution_overrides=resolution_overrides,
                input_method=input_method,
            )
        layout_source = remove_emoji_and_emoticons(normalize_unicode(original_text), self.settings.data_dir).cleaned_text
        restored_layout = restore_terminal_punctuation(layout_source, result.primary_output)
        if restored_layout != result.primary_output:
            result.expanded_abbreviations = _remap_expanded_abbreviation_spans(
                result.expanded_abbreviations, restored_layout, previous_output=result.primary_output)
            result.primary_output = restored_layout
            if result.variants:
                result.variants[0].output = restored_layout
        punctuated_output, self._punctuation_edit = append_question_mark(result.primary_output)
        if punctuated_output != result.primary_output:
            result.primary_output = punctuated_output
            if result.variants:
                result.variants[0].output = punctuated_output
        self._record_usage_stats(result.expanded_abbreviations)
        self._populate_change_metadata(original_text, result)
        return result

    def _populate_change_metadata(
        self,
        original_text: str,
        result: LiveNormalizationResult,
        dataset_output: str | None = None,
        dataset_ambiguities: list[LiveAmbiguity] | None = None,
    ) -> None:
        """Build stable source/output spans for the comparison view.

        ``dataset_output`` is supplied after semantic verification so the
        comparison can distinguish dataset edits from the later AI edits.
        """
        expansions = []
        search_from = 0
        # One fold per text, shared by every span lookup below.
        folded_original = _folded_text_with_index_map(original_text)
        for span in result.expanded_abbreviations:
            abbr = str(span.get("abbr") or "").strip()
            output_start = span.get("start")
            output_end = span.get("end")
            if not abbr or not isinstance(output_start, int) or not isinstance(output_end, int):
                continue
            source_start = _find_folded_token(
                original_text, abbr, search_from, folded=folded_original
            )
            if source_start is None:
                continue
            source_end = source_start + len(abbr)
            search_from = source_end
            span["originalStart"] = source_start
            span["originalEnd"] = source_end
            span["original"] = original_text[source_start:source_end]
            expansions.append((source_start, source_end, output_start, output_end))

        changes: list[Dict[str, object]] = []
        spelling_edits = getattr(self, "_spelling_edits", [])
        # Loop-invariant: the opcode alignment depends only on the two strings,
        # not on the individual edit, so compute it once for the whole list.
        if spelling_edits:
            opcodes = SequenceMatcher(None, self._spelling_output.lower(), result.primary_output.lower(), autojunk=False).get_opcodes()

            def mapped(position, right=False):
                for tag, a, b, c, d in opcodes:
                    if a <= position < b or (right and a < position <= b):
                        return c + position - a if tag == "equal" else (d if right else c)
                return len(result.primary_output)
        for index, edit in enumerate(spelling_edits):
            # Align explicit rule provenance to final output, never classify a
            # diff as a known typo. Case-folding also tolerates sentence casing.
            start = mapped(edit["correctedStart"])
            end = mapped(edit["correctedEnd"], True)
            if result.primary_output[start:end].lower() != edit["replacement"].lower():
                continue
            changes.append(dict(id=f"spelling-{index}", kinds=["spelling"], reason=edit["reason"], confidence=edit["confidence"],
                originalStart=edit["originalStart"], originalEnd=edit["originalEnd"], outputStart=start, outputEnd=end,
                originalText=original_text[edit["originalStart"]:edit["originalEnd"]], outputText=result.primary_output[start:end]))
        if getattr(self, "_punctuation_edit", None) and result.primary_output.rstrip().endswith("?"):
            output_start = len(result.primary_output.rstrip()) - 1
            source_start = len(original_text.rstrip())
            changes.append(dict(id="punctuation-insertion", kinds=["punctuation"], reason="explicit_question_opening",
                originalStart=source_start, originalEnd=source_start, outputStart=output_start, outputEnd=output_start + 1,
                originalText="", outputText="?"))
        explicit = [(item["originalStart"], item["originalEnd"], item["outputStart"], item["outputEnd"]) for item in changes]
        for source_start, source_end, output_start, output_end in expansions:
            provenance = next((span for span in result.expanded_abbreviations
                               if span.get("start") == output_start and span.get("end") == output_end), {})
            changes.append(
                {
                    "id": f"teencode-{source_start}-{output_start}",
                    "kinds": ["teencode"],
                    "source": provenance.get("source"),
                    "candidateId": provenance.get("candidateId"),
                    "revision": provenance.get("revision"),
                    "policyVersion": provenance.get("policyVersion"),
                    "originalStart": source_start,
                    "originalEnd": source_end,
                    "outputStart": output_start,
                    "outputEnd": output_end,
                    "originalText": original_text[source_start:source_end],
                    "outputText": result.primary_output[output_start:output_end],
                }
            )

        comparison_output = dataset_output if dataset_output is not None else result.primary_output
        dataset_to_final = SequenceMatcher(
            None, comparison_output, result.primary_output, autojunk=False
        ).get_opcodes() if dataset_output is not None else []

        def project_dataset_position(position: int, right: bool = False) -> int:
            if dataset_output is None:
                return position
            for tag, source_start, source_end, final_start, final_end in dataset_to_final:
                if source_start <= position < source_end or (right and source_start < position <= source_end):
                    return final_start + position - source_start if tag == "equal" else (final_end if right else final_start)
            return len(result.primary_output)

        for opcode, source_start, source_end, output_start, output_end in SequenceMatcher(
            None, original_text, comparison_output, autojunk=False
        ).get_opcodes():
            if opcode == "equal" or _overlaps_any(
                project_dataset_position(output_start), project_dataset_position(output_end, True),
                [(item[2], item[3]) for item in expansions + explicit]
            ) or _overlaps_any(
                source_start, source_end, [(item[0], item[1]) for item in expansions + explicit]
            ):
                continue
            source_start, source_end, output_start, output_end = _expand_word_change_bounds(
                original_text, comparison_output,
                source_start,
                source_end,
                output_start,
                output_end,
            )
            output_start = project_dataset_position(output_start)
            output_end = project_dataset_position(output_end, True)
            original = original_text[source_start:source_end]
            output = result.primary_output[output_start:output_end]
            kinds = _classify_change(original, output)
            changes.append(
                {
                    "id": f"change-{source_start}-{output_start}",
                    "kinds": kinds,
                    "originalStart": source_start,
                    "originalEnd": source_end,
                    "outputStart": output_start,
                    "outputEnd": output_end,
                    "originalText": original,
                    "outputText": output,
                }
            )
        if dataset_output is not None and dataset_output != result.primary_output:
            # Keep AI provenance local to each edit.  Marking only pre-existing
            # dataset changes loses AI-only edits and breaks when the model
            # changes the length of a dataset replacement.
            dataset_to_source = SequenceMatcher(
                None, original_text, dataset_output, autojunk=False
            ).get_opcodes()

            def source_range_for_dataset(start: int, end: int) -> tuple[int, int]:
                mapped_start = len(original_text)
                mapped_end = mapped_start
                for opcode, source_start, source_end, output_start, output_end in dataset_to_source:
                    if output_start <= start < output_end or (start == end == output_start):
                        mapped_start = source_start if opcode != "equal" else source_start + (start - output_start)
                        break
                for opcode, source_start, source_end, output_start, output_end in dataset_to_source:
                    if output_start < end <= output_end or (start == end == output_end):
                        mapped_end = source_end if opcode != "equal" else source_start + (end - output_start)
                        break
                if mapped_start == len(original_text) and mapped_end == len(original_text):
                    return len(original_text), len(original_text)
                return mapped_start, max(mapped_start, mapped_end)

            ai_ranges: list[tuple[int, int]] = []
            correction_index = 0
            for before, after in getattr(result, "semantic_corrections", []):
                before_text = str(before).strip()
                after_text = str(after).strip()
                if not before_text or not after_text:
                    continue
                dataset_start = dataset_output.find(before_text)
                output_start = result.primary_output.find(after_text)
                if dataset_start < 0 or output_start < 0:
                    continue
                dataset_end = dataset_start + len(before_text)
                output_end = output_start + len(after_text)
                source_start, source_end = source_range_for_dataset(dataset_start, dataset_end)
                ai_kinds = ["ai"]
                if _overlaps_any(source_start, source_end, [(item[0], item[1]) for item in expansions]) or dataset_ambiguities:
                    ai_kinds.append("teencode")
                changes.append(dict(
                    id=f"ai-correction-{correction_index}-{output_start}",
                    kinds=ai_kinds,
                    source="ai_context",
                    originalStart=source_start,
                    originalEnd=source_end,
                    outputStart=output_start,
                    outputEnd=output_end,
                    originalText=original_text[source_start:source_end],
                    outputText=result.primary_output[output_start:output_end],
                ))
                ai_ranges.append((output_start, output_end))
                correction_index += 1

            ai_opcodes = SequenceMatcher(
                None, dataset_output, result.primary_output, autojunk=False
            ).get_opcodes()
            for index, (opcode, dataset_start, dataset_end, output_start, output_end) in enumerate(ai_opcodes):
                if opcode == "equal" or _overlaps_any(output_start, output_end, ai_ranges):
                    continue
                dataset_fragment = dataset_output[dataset_start:dataset_end]
                output_fragment = result.primary_output[output_start:output_end]
                local_ranges = _word_change_ranges(dataset_fragment, output_fragment)
                # AI comparison marks are deliberately word-sized. A model
                # response that changes one token must not paint an entire
                # sentence or paragraph because the provider grouped its diff.
                for part_index, (local_source_start, local_source_end,
                                 local_output_start, local_output_end) in enumerate(local_ranges):
                    absolute_dataset_start = dataset_start + local_source_start
                    absolute_dataset_end = dataset_start + local_source_end
                    absolute_output_start = output_start + local_output_start
                    absolute_output_end = output_start + local_output_end
                    source_start, source_end = source_range_for_dataset(
                        absolute_dataset_start, absolute_dataset_end
                    )
                    ai_kinds = ["ai", "teencode"] if dataset_ambiguities else ["ai"]
                    changes.append(dict(
                        id=f"ai-{index}-{part_index}-{absolute_output_start}",
                        kinds=ai_kinds,
                        source="ai_context",
                        originalStart=source_start,
                        originalEnd=source_end,
                        outputStart=absolute_output_start,
                        outputEnd=absolute_output_end,
                        originalText=original_text[source_start:source_end],
                        outputText=result.primary_output[absolute_output_start:absolute_output_end],
                    ))

        ordered = sorted(changes, key=lambda item: (item["originalStart"], item["outputStart"]))
        merged: list[Dict[str, object]] = []
        for change in ordered:
            if not merged:
                merged.append(change)
                continue
            previous = merged[-1]
            overlaps = _overlaps_any(
                int(change["originalStart"]),
                int(change["originalEnd"]),
                [(int(previous["originalStart"]), int(previous["originalEnd"]))],
            )
            if overlaps and not (
                "teencode" in previous["kinds"] or "teencode" in change["kinds"]
            ):
                previous["originalStart"] = min(previous["originalStart"], change["originalStart"])
                previous["originalEnd"] = max(previous["originalEnd"], change["originalEnd"])
                previous["outputStart"] = min(previous["outputStart"], change["outputStart"])
                previous["outputEnd"] = max(previous["outputEnd"], change["outputEnd"])
                previous["originalText"] = original_text[previous["originalStart"] : previous["originalEnd"]]
                previous["outputText"] = result.primary_output[previous["outputStart"] : previous["outputEnd"]]
                previous["kinds"] = sorted(set(previous["kinds"]) | set(change["kinds"]))
            else:
                merged.append(change)
        result.changes = merged

    def _record_usage_stats(self, expanded_abbreviations: List[Dict[str, object]]) -> None:
        repository = self._usage_stats_repository
        if repository is None:
            return

        pairs = [
            (str(span.get("abbr") or "").strip(), str(span.get("expanded") or "").strip())
            for span in expanded_abbreviations
        ]
        pairs = [(abbr, expanded) for abbr, expanded in pairs if abbr and expanded]
        if not pairs:
            return

        # Skip the whole telemetry path when the table is not deployed, instead
        # of paying one failing round-trip per expanded abbreviation.
        is_ready = getattr(repository, "is_ready", None)
        if callable(is_ready):
            try:
                if not is_ready():
                    return
            except Exception:  # pragma: no cover - defensive
                return

        try:
            # One transaction for the whole request. The per-span version issued
            # a separate MERGE (and commit) for every expanded abbreviation,
            # which meant >1000 round-trips contending on the same few rows for
            # a single long paste.
            record_bulk = getattr(repository, "record_usage_bulk", None)
            if callable(record_bulk):
                record_bulk(pairs, source_kind="live")
                return

            record_usage = getattr(repository, "record_usage", None)
            if not callable(record_usage):
                return
            for abbr, expanded in pairs:
                record_usage(abbr=abbr, expanded_chosen=expanded, source_kind="live")
        except Exception:  # pragma: no cover - telemetry must not break normalization
            logging.getLogger(__name__).warning(
                "Failed to record abbreviation usage", exc_info=True
            )

    def _normalize_live_uncached(
        self,
        text: str,
        submitted_by: Optional[str] = None,
        user_id: Optional[str] = None,
        domain: str = "general",
        resolution_overrides: Optional[Dict[str, str]] = None,
        input_method: str = "paste",
        live_data: object | None = None,
        phrase_index: PhraseIndex | None = None,
        pending_budget: "_PendingBudget | None" = None,
        capitalize: bool = True,
    ) -> LiveNormalizationResult:
        started_at = time.perf_counter()
        overrides = resolution_overrides or {}
        normalized_text = normalize_unicode(text)
        emoji_result = remove_emoji_and_emoticons(normalized_text, self.settings.data_dir)
        cleaned_text = emoji_result.cleaned_text

        diacritic_applied = False
        diacritic_changes: List[tuple] = []
        if self._diacritic_restorer:
            dr = self._diacritic_restorer.restore(cleaned_text)
            if dr.applied:
                cleaned_text = dr.restored_text
                diacritic_applied = True
                diacritic_changes = list(dr.changed_tokens)
        layout = capture_token_layout(cleaned_text)

        if live_data is None:
            live_data = self.pending_service.get_live_normalization_data(
                domain=domain,
                user_id=None,
            )
        abbreviations = live_data.abbreviations
        abbreviation_keys = abbreviations.keys()
        known_words = live_data.dictionary_words
        approved_details = live_data.approved_details

        if phrase_index is None:
            phrase_index = self._build_phrase_index(live_data)
        # One budget for the whole request, shared by the phrase-level and
        # token-level moderation paths.
        budget = pending_budget or _PendingBudget(
            remaining=max(0, self.settings.live_max_pending_submissions)
        )
        phrase_result = self._pipeline.phrase_normalizer.normalize_phrases(
            cleaned_text,
            phrase_index,
            known_words=known_words,
            approved_abbreviations=abbreviations,
            already_pending=budget.submitted_keys,
            domain=domain,
            submitted_by=submitted_by,
            pending_budget=budget,
        )
        tokens = phrase_result.tokens
        consumed = phrase_result.consumed_token_indices
        replacements = phrase_result.token_replacements

        token_groups: List[dict] = []
        error_types: set[str] = set(phrase_result.error_types)
        warnings: List[str] = []
        pending_submissions: List[Dict[str, object]] = _dedupe_pending_submissions(
            list(phrase_result.pending_phrase_submissions)
        )
        phrase_matches_by_start = {
            match.start_token: match for match in phrase_result.phrase_matches
        }
        ambiguity_counts: Dict[str, int] = {}
        submitted_pending_keys: set[str] = {
            str(submission.get("abbr") or "").strip().lower()
            for submission in pending_submissions
            if str(submission.get("abbr") or "").strip()
        }
        submitted_pending_keys |= budget.submitted_keys
        pending_limit_warning_added = False

        if emoji_result.removed_any:
            error_types.add("EMOJI")
        if diacritic_applied:
            error_types.add("DIACRITIC")
        trailing_token_is_open = (
            input_method == "typing" and bool(cleaned_text) and cleaned_text[-1].isalnum()
        )
        last_token_index = len(tokens) - 1
        is_suspected_abbreviation = self._pipeline._is_suspected_abbreviation  # noqa: SLF001
        is_known_word = self._pipeline._is_known_word  # noqa: SLF001

        for token_index, token in enumerate(tokens):
            if token_index in consumed:
                replacement = replacements.get(token_index, "")
                group = {"type": "fixed", "value": replacement}
                match = phrase_matches_by_start.get(token_index)
                if (
                    replacement
                    and match
                    and _is_true_abbreviation(match.matched_phrase, match.expanded)
                ):
                    group["abbr"] = match.matched_phrase
                    group["source"] = "phrase"
                token_groups.append(group)
                continue

            if not token.isalpha():
                token_groups.append({"type": "fixed", "value": token})
                continue

            token_lower = token.lower()
            transformed = normalize_elongated_word(token, known_words, abbreviation_keys)
            transformed_lower = transformed.lower()
            if transformed_lower != token_lower:
                error_types.add("ELONGATION")

            approved = approved_details.get(transformed_lower)
            if approved:
                options = self._merge_options(
                    primary=approved["expanded"],
                    alternatives=approved.get("alternative_expansions", []),
                )
                if approved["expanded"].lower() != transformed_lower:
                    error_types.add("ABBR")
                if len(options) > 1:
                    occurrence = ambiguity_counts.get(transformed_lower, 0)
                    ambiguity_counts[transformed_lower] = occurrence + 1
                    ambiguity_id = f"{transformed_lower}:{occurrence}"
                    contextual_choice = choose_contextual_option(
                        abbr=transformed_lower,
                        options=options,
                        tokens=tokens,
                        token_index=token_index,
                        abbreviations=abbreviations,
                    )
                    # Without strong local evidence, keep the abbreviation in
                    # the output. The first dictionary meaning is not evidence
                    # and must not silently rewrite the user's text.
                    default_selected = (
                        contextual_choice.selected if contextual_choice else transformed
                    )
                    selected = overrides.get(ambiguity_id, default_selected)
                    if selected not in options and selected != transformed:
                        selected = default_selected
                    token_groups.append(
                        {
                            "type": "ambiguous",
                            "value": selected,
                            "abbr": transformed_lower,
                            "token_index": token_index,
                            "options": options,
                            "ambiguity_id": ambiguity_id,
                        }
                    )
                else:
                    group = {"type": "fixed", "value": options[0]}
                    if (
                        options[0].lower() != transformed_lower
                        and _is_true_abbreviation(transformed_lower, options[0])
                    ):
                        group["abbr"] = transformed_lower
                        group["source"] = "token"
                    token_groups.append(group)
                continue

            expanded = expand_abbreviation(transformed, abbreviations)
            expanded_lower = expanded.lower()
            group = {"type": "fixed", "value": expanded}
            if expanded_lower != transformed_lower:
                error_types.add("ABBR")
                if _is_true_abbreviation(transformed_lower, expanded):
                    group["abbr"] = transformed_lower
                    group["source"] = "token"

            should_capture_meaning = is_suspected_abbreviation(
                word=transformed,
                expanded=expanded,
                known_words=known_words,
                abbreviations=abbreviations,
            )
            word_is_known = is_known_word(transformed, known_words, abbreviations)
            if should_capture_meaning and expanded_lower == transformed_lower:
                from app.utils.text_utils import is_protected_literal

                if not is_protected_literal(transformed):
                    occurrence = ambiguity_counts.get(transformed_lower, 0)
                    ambiguity_counts[transformed_lower] = occurrence + 1
                    group.update(type="ambiguous", abbr=transformed_lower,
                                 token_index=token_index, options=[transformed],
                                 ambiguity_id=f"{transformed_lower}:{occurrence}")
            should_defer_pending = trailing_token_is_open and token_index == last_token_index
            should_submit_pending = (
                expanded_lower == transformed_lower
                and not should_defer_pending
                and transformed_lower not in submitted_pending_keys
                and (should_capture_meaning or not word_is_known)
            )
            if should_submit_pending:
                submitted_pending_keys.add(transformed_lower)
                budget.submitted_keys.add(transformed_lower)
                if budget.consume(1):
                    submission = self.pending_service.submit_pending_abbreviation(
                        abbr=transformed,
                        submitted_by=submitted_by,
                        source="live_runtime",
                        domain=domain,
                    )
                    submission_payload = dict(submission)
                    has_suggested = bool(submission_payload.get("has_suggested", False))
                    submission_payload["has_suggested"] = has_suggested
                    submission_payload["needs_user_meaning"] = bool(
                        should_capture_meaning
                        and submission_payload.get("pending_id")
                        and not has_suggested
                    )
                    submission_payload["can_add_more_meanings"] = bool(
                        should_capture_meaning
                        and submission_payload.get("pending_id")
                        and has_suggested
                    )
                    pending_submissions.append(submission_payload)
                    if submission_payload["status"] == "DB_UNAVAILABLE":
                        warnings.append(
                            f"Khong the gui pending cho '{transformed}' vi SQL Server chua san sang."
                        )
                elif not pending_limit_warning_added:
                    pending_limit_warning_added = True
                    error_types.add("PENDING_LIMIT")
                    warnings.append(
                        "Da gioi han so tu viet tat moi duoc gui vao hang cho de giu toc do "
                        "xu ly van ban dai."
                    )
            token_groups.append(group)

        ambiguities = [
            LiveAmbiguity(
                id=group["ambiguity_id"],
                abbr=group["abbr"],
                token_index=group["token_index"],
                options=group["options"],
                selected=group["value"],
            )
            for group in token_groups
            if group["type"] == "ambiguous"
        ]
        primary_output, expanded_abbreviations = self._build_output_with_spans(
            token_groups,
            overrides,
            capitalize=capitalize,
            layout=layout if layout.tokens == tokens else None,
        )
        variants = self._build_variants(
            token_groups,
            overrides,
            capitalize=capitalize,
            layout=layout if layout.tokens == tokens else None,
        )
        if variants:
            primary_output = variants[0].output
        if not variants:
            variants = [LiveVariant(id="variant-0", output=primary_output, is_primary=True)]


        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        semantic_signal = bool(ambiguities or diacritic_applied)
        return LiveNormalizationResult(
            primary_output=primary_output,
            variants=variants,
            ambiguities=ambiguities,
            pending_submissions=_dedupe_pending_submissions(pending_submissions),
            warnings=warnings,
            error_types=sorted(error_types),
            latency_ms=latency_ms,
            phrase_matches=list(phrase_result.phrase_matches),
            diacritic_applied=diacritic_applied,
            diacritic_changes=diacritic_changes,
            semantic_status="not_checked" if semantic_signal else "not_needed",
            semantic_total_chunks=1 if semantic_signal else 0,
            expanded_abbreviations=expanded_abbreviations,
        )

    def _should_use_incremental_segments(
        self,
        text: str,
        resolution_overrides: Optional[Dict[str, str]],
    ) -> bool:
        if resolution_overrides:
            return False
        return len(text.strip()) >= self.settings.live_incremental_min_chars

    def _normalize_incremental_segments(
        self,
        *,
        text: str,
        submitted_by: Optional[str],
        user_id: Optional[str],
        domain: str,
        input_method: str,
    ) -> LiveNormalizationResult:
        started_at = time.perf_counter()
        segments = split_for_incremental_normalization(
            text,
            target_words=self.settings.live_incremental_chunk_words,
        )
        if len(segments) <= 1:
            return self._normalize_live_uncached(
                text=text,
                submitted_by=submitted_by,
                user_id=user_id,
                domain=domain,
                input_method=input_method,
            )

        # Build the live data and phrase trie ONCE for the whole request.
        # Rebuilding the ~2k-phrase trie per segment burned seconds of CPU on a
        # single paste, and every rebuild produced the identical index.
        live_data = self.pending_service.get_live_normalization_data(
            domain=domain,
            user_id=None,
        )
        phrase_index = self._build_phrase_index(live_data)
        budget = _PendingBudget(remaining=max(0, self.settings.live_max_pending_submissions))

        segment_results: list[LiveNormalizationResult] = []
        for index, segment in enumerate(segments):
            segment_input_method = (
                input_method
                if index == len(segments) - 1 and text.strip()[-1].isalnum()
                else "paste"
            )
            cache_key = self._segment_cache_key(
                text=segment.text,
                user_id=user_id,
                domain=domain,
                input_method=segment_input_method,
                dictionary_revision=live_data.revision if hasattr(self.pending_service, "dictionary_revision") else None,
            )
            cached = self._get_cached_segment(cache_key)
            if cached is not None:
                # A cached segment still consumed budget when it was produced,
                # so charge for it — otherwise cache hits sneak past the cap.
                budget.consume(len(cached.pending_submissions))
                for submission in cached.pending_submissions:
                    key = str(submission.get("abbr") or "").strip().lower()
                    if key:
                        budget.submitted_keys.add(key)
                segment_results.append(cached)
                continue

            result = self._normalize_live_uncached(
                text=segment.text,
                submitted_by=submitted_by,
                user_id=user_id,
                domain=domain,
                input_method=segment_input_method,
                live_data=live_data,
                phrase_index=phrase_index,
                pending_budget=budget,
                # Capitalisation is applied once to the joined text; doing it per
                # segment injected a capital letter every ~120 words mid-sentence.
                capitalize=False,
            )
            self._set_cached_segment(cache_key, result)
            segment_results.append(result)

        return self._combine_segment_results(
            segment_results,
            separators=[segment.leading_separator for segment in segments],
            trailing_separator=segments[-1].trailing_separator,
            latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )

    def _combine_segment_results(
        self,
        results: list[LiveNormalizationResult],
        separators: list[str],
        trailing_separator: str,
        latency_ms: float,
    ) -> LiveNormalizationResult:
        primary_parts: list[str] = [separators[0] if separators else ""]
        warnings: list[str] = []
        pending_submissions: list[Dict[str, object]] = []
        error_types: set[str] = set()
        phrase_matches: list[PhraseMatch] = []
        ambiguities: list[LiveAmbiguity] = []
        diacritic_changes: list[tuple] = []
        expanded_abbreviations: list[Dict[str, object]] = []
        token_offset = 0
        char_offset = len(primary_parts[0])

        for segment_index, result in enumerate(results):
            if segment_index > 0:
                separator = separators[segment_index] if segment_index < len(separators) else ""
                primary_parts.append(separator)
                char_offset += len(separator)
            if result.primary_output:
                for span in result.expanded_abbreviations:
                    shifted_span = dict(span)
                    start = shifted_span.get("start")
                    end = shifted_span.get("end")
                    if isinstance(start, int) and isinstance(end, int):
                        shifted_span["start"] = start + char_offset
                        shifted_span["end"] = end + char_offset
                    expanded_abbreviations.append(shifted_span)
                primary_parts.append(result.primary_output)
                char_offset += len(result.primary_output)
            warnings.extend(result.warnings)
            pending_submissions.extend(result.pending_submissions)
            error_types.update(result.error_types)
            diacritic_changes.extend(result.diacritic_changes)
            for match in result.phrase_matches:
                phrase_matches.append(
                    PhraseMatch(
                        start_token=match.start_token + token_offset,
                        end_token=match.end_token + token_offset,
                        matched_phrase=match.matched_phrase,
                        expanded=match.expanded,
                        confidence=match.confidence,
                        source=match.source,
                    )
                )
            for ambiguity in result.ambiguities:
                ambiguity_id = f"s{segment_index}:{ambiguity.id}"
                ambiguities.append(
                    LiveAmbiguity(
                        id=ambiguity_id,
                        abbr=ambiguity.abbr,
                        token_index=ambiguity.token_index + token_offset,
                        options=list(ambiguity.options),
                        selected=ambiguity.selected,
                    )
                )
            token_offset += len(tokenize_for_scan(result.primary_output))

        primary_parts.append(trailing_separator)
        primary_output = capitalize_sentence_starts("".join(primary_parts))
        # Capitalisation preserves length, so offsets are still valid — but the
        # declared `expanded` text must be re-read from the final string or it
        # would disagree with primary_output[start:end] on the first letter.
        for span in expanded_abbreviations:
            start = span.get("start")
            end = span.get("end")
            if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(
                primary_output
            ):
                span["expanded"] = primary_output[start:end]
        pending_submissions = _dedupe_pending_submissions(pending_submissions)
        semantic_total_chunks = sum(result.semantic_total_chunks for result in results)
        semantic_verified_chunks = sum(result.semantic_verified_chunks for result in results)
        semantic_status = "not_needed" if semantic_total_chunks == 0 else "not_checked"

        return LiveNormalizationResult(
            primary_output=primary_output,
            variants=[
                LiveVariant(
                    id="variant-0",
                    output=primary_output,
                    resolutions=[],
                    is_primary=True,
                )
            ],
            ambiguities=ambiguities,
            pending_submissions=pending_submissions,
            warnings=warnings,
            error_types=sorted(error_types),
            latency_ms=latency_ms,
            phrase_matches=phrase_matches,
            diacritic_applied=any(result.diacritic_applied for result in results),
            diacritic_changes=diacritic_changes,
            semantic_status=semantic_status,
            semantic_verified_chunks=semantic_verified_chunks,
            semantic_total_chunks=semantic_total_chunks,
            semantic_from_cache=all(result.semantic_from_cache for result in results),
            expanded_abbreviations=expanded_abbreviations,
        )

    def _segment_cache_key(
        self,
        *,
        text: str,
        user_id: Optional[str],
        domain: str,
        input_method: str,
        dictionary_revision: int | None = None,
    ) -> str:
        return json.dumps(
            {
                "text": text,
                "userId": user_id,
                "domain": domain,
                "inputMethod": input_method,
                "liveDataGeneration": self._live_data_generation() if dictionary_revision is None else dictionary_revision,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    def _live_data_generation(self) -> int:
        revision = getattr(self.pending_service, "dictionary_revision", None)
        if callable(revision):
            return int(revision())
        generation = getattr(self.pending_service, "live_normalization_cache_generation", None)
        if callable(generation):
            return int(generation())
        return PendingAbbreviationService.live_normalization_cache_generation()

    @classmethod
    def _get_cached_segment(cls, cache_key: str) -> LiveNormalizationResult | None:
        with cls._segment_cache_lock:
            result = cls._segment_cache.get(cache_key)
            if result is None:
                return None
            cls._segment_cache.move_to_end(cache_key)
            return result

    def _set_cached_segment(self, cache_key: str, result: LiveNormalizationResult) -> None:
        max_size = max(1, self.settings.live_incremental_cache_size)
        with self._segment_cache_lock:
            self._segment_cache[cache_key] = result
            self._segment_cache.move_to_end(cache_key)
            while len(self._segment_cache) > max_size:
                self._segment_cache.popitem(last=False)

    async def dictionary_is_current(self) -> bool:
        current = await asyncio.to_thread(self._live_data_generation)
        if getattr(self, "_request_dictionary_revision", current) != current:
            return False
        meanings = self._request_meanings
        return not (meanings and meanings.used) or await asyncio.to_thread(meanings.current)

    async def apply_semantic_verification(
        self, result, original_text, word_map=None, on_progress=None,
    ):
        from app.ai.semantic_verifier import SemanticVerifier
        baseline = copy.deepcopy(result)
        meanings = self._request_meanings
        if meanings:
            await asyncio.to_thread(meanings.reuse, original_text, result)
        semantic_signal = bool(result.ambiguities or result.diacritic_applied)
        if isinstance(self._semantic_verifier, SemanticVerifier) and not semantic_signal and len(original_text.strip()) < 20:
            result.semantic_status = "not_needed"
            result.semantic_status_reason = "no_semantic_signal"
            result.semantic_total_chunks = 0
        elif isinstance(self._semantic_verifier, SemanticVerifier) or not (
            meanings and meanings.used and not result.ambiguities and not result.diacritic_applied
        ):
            result = await self._apply_semantic_verification(result, original_text, word_map, on_progress)
        if not await self.dictionary_is_current():
            baseline.semantic_status = "not_checked"
            baseline.semantic_status_reason = "dictionary_changed"
            return baseline
        # Preserve the dataset snapshot so the final metadata can distinguish
        # edits introduced by semantic verification from dataset edits.
        self._populate_change_metadata(
            original_text,
            result,
            dataset_output=baseline.primary_output,
            dataset_ambiguities=baseline.ambiguities,
        )
        return result

    async def _apply_semantic_verification(
        self,
        result: LiveNormalizationResult,
        original_text: str,
        word_map: dict[str, list[str]] | None = None,
        on_progress: Callable | None = None,
    ) -> LiveNormalizationResult:
        """Apply AI semantic verification to a normalization result.

        Must be called explicitly after ``normalize_live`` by an async handler.
        Modifies and returns the result with semantic verification fields.
        """
        if not result.primary_output.strip():
            return result

        if self._semantic_verifier is None:
            result.semantic_status = "unavailable"
            result.semantic_status_reason = "provider_unavailable"
            return result

        from app.ai.semantic_verifier import SemanticVerifier

        verifier: SemanticVerifier = self._semantic_verifier  # type: ignore[assignment]
        dataset_output = result.primary_output

        if not verifier.is_available():
            result.semantic_status = "unavailable"
            result.semantic_status_reason = "provider_unavailable"
            return result

        # Collect ambiguous diacritic candidates from the original text
        diacritic_candidates: dict[str, list[str]] | None = None
        if result.diacritic_applied:
            diacritic_candidates = {}
            if word_map:
                diacritic_candidates.update(collect_ambiguous_diacritics(original_text, word_map))
            diacritic_candidates.update(_build_diacritic_change_options(result.diacritic_changes))
            if not diacritic_candidates:
                diacritic_candidates = None

        # Collect abbreviation ambiguities
        abbr_options: dict[str, list[str]] | None = None
        if result.ambiguities:
            abbr_options = {a.abbr: a.options for a in result.ambiguities}

        try:
            verification = await verifier.verify(
                text=result.primary_output,
                diacritic_candidates=diacritic_candidates,
                abbreviation_options=abbr_options,
                **({"cache_namespace": str(getattr(self, "_request_dictionary_revision", 0)) + ":" +
                   str(self._request_meanings.revision if self._request_meanings else 0),
                   "review_all": True, "source_text": original_text}
                   if isinstance(verifier, SemanticVerifier) else {}),
                **({"on_progress": on_progress} if on_progress else {}),
            )

            verified_text = capitalize_sentence_starts(verification.verified_text)
            if not preserves_punctuation(result.primary_output, verified_text):
                result.semantic_status = "uncertain"
                result.semantic_status_reason = "punctuation_policy"
                return result
            verified_chunks = int(getattr(verification, "verified_chunks", 0) or 0)
            total_chunks = max(
                verified_chunks,
                int(getattr(verification, "total_chunks", 1) or 1),
            )

            if not await self.dictionary_is_current():
                result.semantic_status = "not_checked"
                result.semantic_status_reason = "dictionary_changed"
                return result
            verification_status = str(
                getattr(verification, "status", "verified" if verified_chunks else "not_checked")
            )
            ai_confident = (
                verification.confidence >= self.settings.semantic_verify_confidence_threshold
            )
            # A checked teencode proposal can be shown as an inference below the
            # confidence threshold. Zero-call results must never overwrite text.
            ai_answered = verified_chunks > 0
            # ``validated_output`` means the provider response passed shape and
            # protected-region checks; it is not a quality signal. Never let a
            # low-confidence full-text rewrite replace the dataset baseline.
            # The product policy makes one deliberate exception: a valid
            # low-confidence abbreviation/teencode meaning may be applied with
            # an ``uncertain`` label.
            ai_usable = ai_confident or (
                bool(abbr_options)
                and bool(getattr(verification, "validated_output", False))
                and verification_status in {"verified", "uncertain", "partial"}
            )
            text_changed = (
                verified_text != result.primary_output and ai_answered and ai_usable
            )

            if text_changed or (verification.corrections and ai_answered and ai_usable):
                corrections = list(verification.corrections)
                if text_changed and not corrections:
                    corrections = [(result.primary_output, verified_text)]
                if text_changed:
                    result.expanded_abbreviations = _remap_expanded_abbreviation_spans(
                        result.expanded_abbreviations,
                        verified_text,
                        corrections=corrections,
                        previous_output=result.primary_output,
                    )
                result.primary_output = verified_text
                result.semantic_corrections = corrections
                result.error_types = sorted({*result.error_types, "SEMANTIC"})
                for variant in result.variants:
                    if variant.is_primary:
                        variant.output = verified_text

            if self._request_meanings and ai_answered and ai_usable and abbr_options:
                await asyncio.to_thread(self._request_meanings.capture, original_text, abbr_options, verification, result)
            if ai_answered and ai_usable and abbr_options:
                # Cache hits still carry AI provenance, but never create evidence.
                for before, after in verification.corrections:
                    abbr = str(before).strip().lower()
                    if abbr not in {key.lower() for key in abbr_options} or not str(after).strip():
                        continue
                    matches = list(re.finditer(rf"(?<!\w){re.escape(str(after))}(?!\w)", result.primary_output, re.I))
                    if len(matches) == 1 and not any(str(s["abbr"]).lower() == abbr for s in result.expanded_abbreviations):
                        match = matches[0]
                        result.expanded_abbreviations.append(dict(abbr=abbr, expanded=match[0],
                            start=match.start(), end=match.end(), source="ai_inferred"))
            result.semantic_confidence = verification.confidence
            result.semantic_verified_chunks = verified_chunks
            result.semantic_total_chunks = total_chunks
            result.semantic_from_cache = bool(getattr(verification, "from_cache", False))
            result.semantic_verified = False
            if verification_status == "quota":
                result.semantic_status = "partial" if ai_answered else "quota"
                result.semantic_status_reason = "rate_limited"
            elif verification_status == "error":
                result.semantic_status = "partial" if ai_answered else "error"
                result.semantic_status_reason = str(
                    getattr(verification, "reason", None) or "provider_error"
                )
            elif verification_status == "uncertain" or not ai_confident:
                result.semantic_status = "uncertain"
                result.semantic_status_reason = "low_confidence"
                if text_changed and abbr_options:
                    result.semantic_status_reason = "ai_inferred_meaning"
            elif ai_answered and verified_chunks >= total_chunks:
                result.semantic_status = "verified"
                result.semantic_status_reason = "fallback_model" if getattr(verification, "fallback_used", False) else "provider_checked"
                result.semantic_verified = True
            elif ai_answered:
                result.semantic_status = "partial"
                result.semantic_status_reason = "chunk_scope_incomplete"
            else:
                result.semantic_status = "not_checked"
                result.semantic_status_reason = str(
                    getattr(verification, "reason", None) or "no_provider_result"
                )

            if ai_usable and ai_answered and abbr_options:
                remaining_words = set(re.findall(r"\w+", result.primary_output.lower()))
                result.ambiguities = [a for a in result.ambiguities if a.abbr.lower() in remaining_words]
                if result.ambiguities and result.semantic_status == "verified":
                    result.semantic_status = "uncertain"
                    result.semantic_status_reason = "unresolved_meaning"
                    result.semantic_verified = False
                result.variants = [
                    LiveVariant(
                        id="ai-context",
                        output=result.primary_output,
                        resolutions=[],
                        is_primary=True,
                    )
                ]

        except (AIError, json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            # Expected failure modes from the AI client and JSON parsing — fall
            # back to the rule-based result and keep serving the request.
            logging.getLogger(__name__).warning(
                "Semantic verification failed; returning rule-based output",
                exc_info=True,
            )
            result.semantic_status = "quota" if isinstance(exc, AIRateLimitError) else "error"
            result.semantic_status_reason = (
                "rate_limited" if isinstance(exc, AIRateLimitError) else "provider_error"
            )
            result.semantic_verified = False

        self._populate_change_metadata(original_text, result, dataset_output=dataset_output)

        return result

    def _build_phrase_index(self, live_data) -> PhraseIndex:
        overrides = entries_from_phrase_dict(getattr(live_data, "phrase_overrides", {}) or {})
        db_phrases = entries_from_phrase_dict(getattr(live_data, "db_phrases", {}) or {})
        mined = entries_from_phrase_dict(getattr(live_data, "mined_phrases", {}) or {})
        if not (overrides or db_phrases or mined):
            return PhraseIndex.empty(max_ngram=self.settings.phrase_max_ngram)
        return PhraseIndex.build(
            overrides=overrides,
            db_phrases=db_phrases,
            mined=mined,
            max_ngram=self.settings.phrase_max_ngram,
        )

    @staticmethod
    def _merge_options(primary: str, alternatives: List[str]) -> List[str]:
        options: List[str] = []
        for candidate in [primary, *alternatives]:
            cleaned = str(candidate or "").strip()
            if cleaned and cleaned not in options:
                options.append(cleaned)
        return options

    @staticmethod
    def _build_output_with_spans(
        token_groups: List[dict],
        overrides: Dict[str, str],
        capitalize: bool = True,
        layout: TokenLayout | None = None,
    ) -> tuple[str, List[Dict[str, object]]]:
        parts: List[str] = [layout.prefix if layout else ""]
        spans: List[Dict[str, object]] = []
        cursor = len(parts[0])
        previous_index: int | None = None

        for index, group in enumerate(token_groups):
            value = str(group.get("value") or "")
            if group["type"] == "ambiguous":
                selected = overrides.get(group["ambiguity_id"], value)
                value = selected if selected in group["options"] else value

            if not value:
                continue
            if previous_index is not None:
                if layout and index - 1 < len(layout.separators):
                    separator = preserve_separator(layout.separators[index - 1], value)
                else:
                    separator = " "
                parts.append(separator)
                cursor += len(separator)

            start = cursor
            parts.append(value)
            cursor += len(value)
            previous_index = index
            abbr = str(group.get("abbr") or "").strip()
            if abbr and value and start < cursor and _is_true_abbreviation(abbr, value):
                spans.append(
                    {
                        "abbr": abbr,
                        "expanded": value,
                        "start": start,
                        "end": cursor,
                        "source": str(group.get("source") or "token"),
                    }
                )

        if layout:
            parts.append(layout.suffix)
        joined = "".join(parts)
        output = capitalize_sentence_starts(joined) if capitalize else joined
        for span in spans:
            start = span["start"]
            end = span["end"]
            if isinstance(start, int) and isinstance(end, int):
                span["expanded"] = output[start:end]
        return output, spans

    def _build_variants(
        self,
        token_groups: List[dict],
        overrides: Dict[str, str],
        capitalize: bool = True,
        layout: TokenLayout | None = None,
    ) -> List[LiveVariant]:
        def _finish(tokens: List[str]) -> str:
            joined = join_scan_tokens(
                tokens,
                separators=layout.separators if layout else None,
                prefix=layout.prefix if layout else "",
                suffix=layout.suffix if layout else "",
            )
            return capitalize_sentence_starts(joined) if capitalize else joined

        ambiguous_groups = [group for group in token_groups if group["type"] == "ambiguous"]
        if not ambiguous_groups:
            return []

        if len(ambiguous_groups) > self.settings.live_variant_max_ambiguities:
            tokens: List[str] = []
            resolutions: List[VariantResolution] = []
            for group in token_groups:
                if group["type"] != "ambiguous":
                    tokens.append(group["value"])
                    continue
                selected = overrides.get(group["ambiguity_id"], group["value"])
                if selected not in group["options"]:
                    selected = group["value"]
                tokens.append(selected)
                resolutions.append(
                    VariantResolution(
                        ambiguity_id=group["ambiguity_id"],
                        meaning=selected,
                    )
                )
            return [
                LiveVariant(
                    id="variant-0",
                    output=_finish(tokens),
                    resolutions=resolutions,
                    is_primary=True,
                )
            ]

        option_groups = [group["options"] for group in ambiguous_groups]
        primary_values: List[str] = []
        for group in ambiguous_groups:
            selected = overrides.get(group["ambiguity_id"], group["value"])
            # Falls back to group["value"] — the SAME fallback used by
            # _build_output_with_spans. Falling back to options[0] here made the
            # primary variant diverge from the string the spans were measured
            # against, so every offset after a stale override was wrong.
            primary_values.append(selected if selected in group["options"] else group["value"])
        primary_signature = tuple(primary_values)
        combinations = [primary_signature]
        for combination in itertools.islice(itertools.product(*option_groups), 8):
            if combination != primary_signature:
                combinations.append(combination)
            if len(combinations) == 8:
                break

        variants: List[LiveVariant] = []
        for index, combination in enumerate(combinations):
            tokens: List[str] = []
            resolutions: List[VariantResolution] = []
            ambiguity_pointer = 0
            for group in token_groups:
                if group["type"] != "ambiguous":
                    tokens.append(group["value"])
                    continue
                selected = combination[ambiguity_pointer]
                tokens.append(selected)
                resolutions.append(
                    VariantResolution(
                        ambiguity_id=group["ambiguity_id"],
                        meaning=selected,
                    )
                )
                ambiguity_pointer += 1

            signature = tuple(resolution.meaning for resolution in resolutions)
            variants.append(
                LiveVariant(
                    id=f"variant-{index}",
                    output=_finish(tokens),
                    resolutions=resolutions,
                    is_primary=signature == primary_signature,
                )
            )

        variants.sort(key=lambda variant: (not variant.is_primary, variant.id))
        return variants


def _build_diacritic_change_options(changes: List[tuple]) -> dict[str, list[str]]:
    options_by_token: dict[str, list[str]] = {}
    punctuation = ".,!?;:\"'()[]{}\u2026"
    for original, restored in changes:
        key = str(original).lower().strip(punctuation)
        if not key:
            continue
        options: list[str] = []
        for candidate in (str(restored).strip(), str(original).strip()):
            if candidate and candidate not in options:
                options.append(candidate)
        if options:
            options_by_token[key] = options
    return options_by_token
