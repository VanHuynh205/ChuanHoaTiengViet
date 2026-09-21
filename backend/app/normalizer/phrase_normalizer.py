"""Phrase-level normalizer (Phase 2 of ROADMAP_v2).

Runs *before* the existing token-level abbreviation expansion. When a
multi-token phrase matches the index it is rewritten in one shot and the
underlying tokens are marked as consumed so the token loop does not
double-expand them.

The submission heuristic is intentionally strict: a span only goes to the
pending table when *every* alphabetic token in it looks like an abbreviation
(unknown to the dictionary and not already approved). This keeps phrase
pendings out of the noisy "user paragraph contains a typo" path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Protocol, Sequence, Set

from app.config import Settings
from app.data_manager.pending_service import PendingAbbreviationService
from app.normalizer.phrase_index import PhraseIndex, PhraseSpan
from app.utils.text_utils import tokenize_for_scan


class _SupportsConsume(Protocol):
    """A moderation-write budget shared across one request."""

    def consume(self, count: int = 1) -> bool: ...


@dataclass(frozen=True)
class PhraseMatch:
    """Public-facing record of one matched phrase."""

    start_token: int
    end_token: int  # exclusive
    matched_phrase: str
    expanded: str
    confidence: float
    source: str


@dataclass
class PhraseNormalizationResult:
    """Result of a phrase pass.

    ``consumed_token_indices`` lets the token-level loop skip indices that a
    phrase already covered. ``token_replacements`` maps each consumed token
    index to the rewritten chunk; the *first* index in a span carries the
    full expanded phrase, the rest carry the empty string.
    """

    tokens: List[str] = field(default_factory=list)
    phrase_matches: List[PhraseMatch] = field(default_factory=list)
    consumed_token_indices: Set[int] = field(default_factory=set)
    token_replacements: Dict[int, str] = field(default_factory=dict)
    pending_phrase_submissions: List[Dict[str, object]] = field(default_factory=list)
    error_types: List[str] = field(default_factory=list)
    fallback_to_token_level: bool = False


class PhraseNormalizer:
    """Coordinates the phrase index, pipeline integration, and pending submissions."""

    _PENDING_SOURCE = "phrase_runtime"
    _MIN_PHRASE_TOKENS = 2

    def __init__(
        self,
        settings: Settings,
        pending_service: PendingAbbreviationService,
    ) -> None:
        self.settings = settings
        self.pending_service = pending_service

    # ------------------------------------------------------------------
    # Token utilities
    # ------------------------------------------------------------------

    @staticmethod
    def alpha_token_pairs(tokens: Sequence[str]) -> list[tuple[int, str]]:
        """Return ``(original_index, lowercase_token)`` for every alpha token."""
        return [(idx, tok.lower()) for idx, tok in enumerate(tokens) if tok.isalpha()]

    @staticmethod
    def join_phrase_key(tokens: Sequence[str]) -> str:
        """Lowercased, underscore-joined key used as the pending phrase ``abbr``."""
        return "_".join(tok.lower() for tok in tokens if tok)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def normalize_phrases(
        self,
        text: str,
        index: PhraseIndex,
        *,
        known_words: Set[str],
        approved_abbreviations: Mapping[str, str],
        already_pending: Optional[Set[str]] = None,
        domain: str = "general",
        submitted_by: Optional[str] = None,
        pending_budget: Optional["_SupportsConsume"] = None,
    ) -> PhraseNormalizationResult:
        tokens = tokenize_for_scan(text)
        result = PhraseNormalizationResult(tokens=list(tokens))
        seen_phrase_keys: Set[str] = already_pending if already_pending is not None else set()

        if not tokens:
            return result

        if not index.is_empty():
            alpha_pairs = self.alpha_token_pairs(tokens)
            spans = index.scan(alpha_pairs)
            for span in spans:
                self._record_match(span, tokens, result)
        else:
            spans = []

        self._collect_phrase_pendings(
            pending_budget=pending_budget,
            tokens=tokens,
            spans=spans,
            result=result,
            known_words=known_words,
            approved_abbreviations=approved_abbreviations,
            already_pending=seen_phrase_keys,
            domain=domain,
            submitted_by=submitted_by,
        )
        return result

    # ------------------------------------------------------------------
    # Span -> rewrite plan
    # ------------------------------------------------------------------

    def _record_match(
        self,
        span: PhraseSpan,
        tokens: Sequence[str],
        result: PhraseNormalizationResult,
    ) -> None:
        for idx in range(span.start_token, span.end_token):
            result.consumed_token_indices.add(idx)
            result.token_replacements[idx] = ""
        result.token_replacements[span.start_token] = span.expanded
        result.phrase_matches.append(
            PhraseMatch(
                start_token=span.start_token,
                end_token=span.end_token,
                matched_phrase=span.matched_phrase,
                expanded=span.expanded,
                confidence=span.confidence,
                source=span.source,
            )
        )
        if "PHRASE" not in result.error_types:
            result.error_types.append("PHRASE")

    # ------------------------------------------------------------------
    # Strict pending heuristic
    # ------------------------------------------------------------------

    def _collect_phrase_pendings(
        self,
        *,
        tokens: Sequence[str],
        spans: Sequence[PhraseSpan],
        result: PhraseNormalizationResult,
        known_words: Set[str],
        approved_abbreviations: Mapping[str, str],
        already_pending: Set[str],
        domain: str,
        submitted_by: Optional[str],
        pending_budget: Optional["_SupportsConsume"] = None,
    ) -> None:
        max_ngram = max(2, int(self.settings.phrase_max_ngram))
        consumed = set(result.consumed_token_indices)
        n = len(tokens)
        i = 0
        while i < n:
            tok = tokens[i]
            if i in consumed or not tok.isalpha():
                i += 1
                continue

            run: list[int] = []
            j = i
            while j < n and tokens[j].isalpha() and j not in consumed:
                run.append(j)
                j += 1
            if len(run) >= self._MIN_PHRASE_TOKENS:
                self._maybe_submit_run(
                    run=run,
                    tokens=tokens,
                    max_ngram=max_ngram,
                    known_words=known_words,
                    approved_abbreviations=approved_abbreviations,
                    already_pending=already_pending,
                    pending_budget=pending_budget,
                    result=result,
                    domain=domain,
                    submitted_by=submitted_by,
                )
            i = j if j > i else i + 1

    def _maybe_submit_run(
        self,
        *,
        run: Sequence[int],
        tokens: Sequence[str],
        max_ngram: int,
        known_words: Set[str],
        approved_abbreviations: Mapping[str, str],
        already_pending: Set[str],
        result: PhraseNormalizationResult,
        domain: str,
        submitted_by: Optional[str],
        pending_budget: Optional["_SupportsConsume"] = None,
    ) -> None:
        # Strict heuristic per plan: every token must look like an abbreviation
        # (not in dictionary, not already an approved single-token abbr).
        run_tokens = [tokens[idx] for idx in run]
        for tok in run_tokens:
            lowered = tok.lower()
            if lowered in known_words:
                return
            if lowered in approved_abbreviations:
                return

        # Cap span length to phrase_max_ngram so we never submit absurd 10-token rows.
        capped = run_tokens[: min(len(run_tokens), max_ngram)]
        if len(capped) < self._MIN_PHRASE_TOKENS:
            return

        key = self.join_phrase_key(capped)
        if not key or key in already_pending:
            return
        already_pending.add(key)

        # When a shared budget is supplied the cap spans the WHOLE request;
        # otherwise fall back to the per-call limit.
        if pending_budget is not None:
            allowed = bool(pending_budget.consume(1))
        else:
            allowed = len(result.pending_phrase_submissions) < max(
                0, self.settings.live_max_pending_submissions
            )
        if not allowed:
            if "PENDING_LIMIT" not in result.error_types:
                result.error_types.append("PENDING_LIMIT")
            return

        submission = self.pending_service.submit_pending_abbreviation(
            abbr=key,
            submitted_by=submitted_by,
            source=self._PENDING_SOURCE,
            domain=domain,
        )
        payload = dict(submission)
        payload.setdefault("abbr", key)
        payload["matched_phrase"] = " ".join(tok.lower() for tok in capped)
        payload["is_phrase"] = True
        result.pending_phrase_submissions.append(payload)
