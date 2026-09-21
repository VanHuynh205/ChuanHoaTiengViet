"""Multi-token phrase index used by the phrase-level normalizer.

The index is a trie keyed by lowercased *word tokens* (not characters), so a
phrase like ``"đk hp"`` is stored as the path ``đk -> hp`` and matches a
sequence of two consecutive alphabetic tokens.

``PhraseIndex.scan`` walks an alpha-token sequence and returns the
non-overlapping longest-prefix matches. Callers feed it the indices of
*alphabetic* tokens; `start_token`/`end_token` come back as positions in the
original token list (so the caller can mark consumed tokens cheaply).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, List, Mapping, Sequence

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PhraseEntry:
    """A single phrase definition contributed by one of the data sources."""

    expanded: str
    source: str
    confidence: float = 1.0


@dataclass(frozen=True)
class PhraseSpan:
    """A successful match in an alpha-token sequence."""

    start_token: int
    end_token: int  # exclusive, in the *original* token list
    matched_phrase: str
    expanded: str
    source: str
    confidence: float


@dataclass
class _Node:
    children: dict[str, "_Node"] = field(default_factory=dict)
    entry: PhraseEntry | None = None
    depth: int = 0


class PhraseIndex:
    """Frozen, read-only trie over space-joined lowercase phrases.

    Sources are merged with priority ``override > db > mined``: when two
    sources define the same phrase, the higher-priority entry wins so a
    curated override is never shadowed by a mined statistic.
    """

    # ``db_override`` is what PendingAbbreviationService tags admin-managed
    # rows from dbo.phrase_overrides with. It was missing here, so it scored 0
    # and lost to every mined statistic — admin edits silently had no effect.
    _SOURCE_PRIORITY: dict[str, int] = {
        "db_override": 4,
        "override": 3,
        "db": 2,
        "mined": 1,
    }

    def __init__(self, root: _Node, max_ngram: int) -> None:
        self._root = root
        self._max_ngram = max_ngram

    @classmethod
    def build(
        cls,
        *,
        overrides: Mapping[str, PhraseEntry] | None = None,
        db_phrases: Mapping[str, PhraseEntry] | None = None,
        mined: Mapping[str, PhraseEntry] | None = None,
        max_ngram: int = 5,
    ) -> "PhraseIndex":
        if max_ngram < 2:
            raise ValueError("max_ngram must be >= 2 (phrases need >=2 tokens)")

        root = _Node()
        max_depth = 0
        for batch in (mined or {}, db_phrases or {}, overrides or {}):
            for phrase, entry in batch.items():
                tokens = _split_phrase(phrase)
                if not tokens or len(tokens) > max_ngram or len(tokens) < 2:
                    continue
                node = root
                for tok in tokens:
                    node = node.children.setdefault(tok, _Node())
                node.depth = len(tokens)
                if node.entry is None or cls._priority(entry.source) >= cls._priority(
                    node.entry.source
                ):
                    node.entry = entry
                if len(tokens) > max_depth:
                    max_depth = len(tokens)
        return cls(root=root, max_ngram=min(max_ngram, max_depth or max_ngram))

    @classmethod
    def empty(cls, max_ngram: int = 5) -> "PhraseIndex":
        return cls(root=_Node(), max_ngram=max_ngram)

    @classmethod
    def _priority(cls, source: str) -> int:
        priority = cls._SOURCE_PRIORITY.get(source)
        if priority is None:
            _LOGGER.warning(
                "Unknown phrase source %r ranks below every known source; "
                "add it to PhraseIndex._SOURCE_PRIORITY.",
                source,
            )
            return 0
        return priority

    def __len__(self) -> int:
        return _count(self._root)

    def is_empty(self) -> bool:
        return not self._root.children

    @property
    def max_ngram(self) -> int:
        return self._max_ngram

    def scan(self, alpha_tokens: Sequence[tuple[int, str]]) -> List[PhraseSpan]:
        """Return non-overlapping longest-prefix matches.

        ``alpha_tokens`` is a sequence of ``(original_index, lowercased_token)``
        pairs. Indices in the result refer back to the original token list.
        """
        spans: List[PhraseSpan] = []
        i = 0
        n = len(alpha_tokens)
        while i < n:
            best: tuple[int, _Node] | None = None
            node = self._root
            j = i
            steps = 0
            while j < n and steps < self._max_ngram:
                token = alpha_tokens[j][1]
                child = node.children.get(token)
                if child is None:
                    break
                node = child
                j += 1
                steps += 1
                if node.entry is not None:
                    best = (j, node)
            if best is not None:
                end_alpha, terminal = best
                start_orig = alpha_tokens[i][0]
                end_orig = alpha_tokens[end_alpha - 1][0] + 1
                matched = " ".join(tok for _, tok in alpha_tokens[i:end_alpha])
                entry = terminal.entry
                if entry is None:
                    i += 1
                    continue
                spans.append(
                    PhraseSpan(
                        start_token=start_orig,
                        end_token=end_orig,
                        matched_phrase=matched,
                        expanded=entry.expanded,
                        source=entry.source,
                        confidence=entry.confidence,
                    )
                )
                i = end_alpha
            else:
                i += 1
        return spans


def _split_phrase(phrase: str) -> list[str]:
    return [tok for tok in phrase.strip().lower().split() if tok]


def _count(node: _Node) -> int:
    total = 1 if node.entry is not None else 0
    for child in node.children.values():
        total += _count(child)
    return total


def entries_from_mapping(
    mapping: Mapping[str, str], source: str, confidence: float = 1.0
) -> dict[str, PhraseEntry]:
    """Lift a plain ``{phrase: expanded}`` dict into ``PhraseEntry`` objects."""
    return {
        phrase: PhraseEntry(expanded=expanded, source=source, confidence=confidence)
        for phrase, expanded in mapping.items()
        if phrase and expanded
    }


def _coerce_confidence(value: object) -> float:
    # ``0`` is a valid confidence and must not be confused with "missing"
    # (the old ``value or 1.0`` silently upgraded an explicit 0 to 1.0).
    if value is None or value == "":
        return 1.0
    if isinstance(value, (int, float, str, bytes, bytearray)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 1.0
    return 1.0


def entries_from_phrase_dict(
    phrase_dict: Mapping[str, Mapping[str, object]],
) -> dict[str, PhraseEntry]:
    """Lift ``{phrase: {expanded, source, confidence}}`` into ``PhraseEntry`` objects."""
    out: dict[str, PhraseEntry] = {}
    for phrase, payload in phrase_dict.items():
        expanded = str(payload.get("expanded") or "").strip()
        if not phrase or not expanded:
            continue
        source = str(payload.get("source") or "override")
        confidence = _coerce_confidence(payload.get("confidence", 1.0))
        out[phrase] = PhraseEntry(expanded=expanded, source=source, confidence=confidence)
    return out


def entries_from_records(records: Iterable[Mapping[str, object]]) -> dict[str, PhraseEntry]:
    """Lift JSON ``[{phrase, expanded, source?, confidence?}]`` records."""
    out: dict[str, PhraseEntry] = {}
    for rec in records:
        phrase = str(rec.get("phrase") or "").strip().lower()
        expanded = str(rec.get("expanded") or "").strip()
        if not phrase or not expanded:
            continue
        source = str(rec.get("source") or "override")
        confidence = _coerce_confidence(rec.get("confidence", 1.0))
        out[phrase] = PhraseEntry(expanded=expanded, source=source, confidence=confidence)
    return out
