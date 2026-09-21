"""Tests for app.normalizer.phrase_index."""

from __future__ import annotations

import pytest

from app.normalizer.phrase_index import (
    PhraseEntry,
    PhraseIndex,
    PhraseSpan,
    entries_from_mapping,
    entries_from_phrase_dict,
    entries_from_records,
)


def _entry(expanded: str, source: str = "override", confidence: float = 1.0) -> PhraseEntry:
    return PhraseEntry(expanded=expanded, source=source, confidence=confidence)


@pytest.mark.unit
def test_empty_index_matches_nothing() -> None:
    index = PhraseIndex.empty()
    assert index.is_empty()
    assert len(index) == 0
    assert index.scan([(0, "đk"), (1, "hp")]) == []


@pytest.mark.unit
def test_single_phrase_match() -> None:
    index = PhraseIndex.build(
        overrides={"đk hp": _entry("đăng ký học phần")},
        max_ngram=5,
    )
    spans = index.scan([(0, "đk"), (1, "hp")])
    assert len(spans) == 1
    assert spans[0] == PhraseSpan(
        start_token=0,
        end_token=2,
        matched_phrase="đk hp",
        expanded="đăng ký học phần",
        source="override",
        confidence=1.0,
    )


@pytest.mark.unit
def test_longest_match_wins() -> None:
    index = PhraseIndex.build(
        overrides={
            "đk hp": _entry("đăng ký học phần"),
            "đk hp khẩn": _entry("đăng ký học phần khẩn cấp"),
        },
        max_ngram=5,
    )
    spans = index.scan([(0, "đk"), (1, "hp"), (2, "khẩn")])
    assert len(spans) == 1
    assert spans[0].end_token == 3
    assert spans[0].expanded == "đăng ký học phần khẩn cấp"


@pytest.mark.unit
def test_no_overlap_advances_past_match() -> None:
    index = PhraseIndex.build(
        overrides={"ko bt": _entry("không biết"), "bt nay": _entry("biết nay")},
        max_ngram=5,
    )
    spans = index.scan([(0, "ko"), (1, "bt"), (2, "nay")])
    assert [(s.start_token, s.end_token) for s in spans] == [(0, 2)]


@pytest.mark.unit
def test_priority_override_beats_mined() -> None:
    index = PhraseIndex.build(
        overrides={"đk hp": _entry("đăng ký học phần", source="override")},
        mined={"đk hp": _entry("dang ky hoc phan", source="mined", confidence=0.5)},
        max_ngram=5,
    )
    spans = index.scan([(0, "đk"), (1, "hp")])
    assert spans[0].expanded == "đăng ký học phần"
    assert spans[0].source == "override"


@pytest.mark.unit
def test_max_ngram_caps_walk() -> None:
    index = PhraseIndex.build(
        overrides={"a b c d": _entry("expanded4")},
        max_ngram=3,
    )
    assert index.is_empty() or len(index) == 0
    assert index.scan([(0, "a"), (1, "b"), (2, "c"), (3, "d")]) == []


@pytest.mark.unit
def test_build_rejects_max_ngram_below_two() -> None:
    with pytest.raises(ValueError):
        PhraseIndex.build(overrides={"a": _entry("alpha")}, max_ngram=1)


@pytest.mark.unit
def test_build_skips_single_token_or_too_long_phrases() -> None:
    index = PhraseIndex.build(
        overrides={
            "a": _entry("alpha"),
            "x y z w q t": _entry("six"),
            "ok la": _entry("hai token"),
        },
        max_ngram=3,
    )
    assert index.scan([(0, "a")]) == []
    spans = index.scan([(0, "ok"), (1, "la")])
    assert spans[0].expanded == "hai token"


@pytest.mark.unit
def test_alpha_index_offsets_translate_to_original_indices() -> None:
    index = PhraseIndex.build(
        overrides={"đk hp": _entry("đăng ký học phần")},
        max_ngram=3,
    )
    spans = index.scan([(2, "đk"), (4, "hp")])
    assert spans[0].start_token == 2
    assert spans[0].end_token == 5


@pytest.mark.unit
def test_entries_from_mapping_helper() -> None:
    entries = entries_from_mapping({"a b": "alpha beta"}, source="db", confidence=0.8)
    assert entries == {"a b": PhraseEntry(expanded="alpha beta", source="db", confidence=0.8)}


@pytest.mark.unit
def test_entries_from_records_helper() -> None:
    entries = entries_from_records(
        [
            {"phrase": "a b", "expanded": "alpha", "source": "mined", "confidence": 0.5},
            {"phrase": "", "expanded": "skip"},
            {"phrase": "x y", "expanded": ""},
            {"phrase": "u v", "expanded": "uv", "confidence": "bad"},
        ]
    )
    assert "a b" in entries
    assert "u v" in entries
    assert entries["u v"].confidence == 1.0


@pytest.mark.unit
def test_entries_from_phrase_dict_helper() -> None:
    entries = entries_from_phrase_dict(
        {
            "a b": {"expanded": "alpha", "source": "override", "confidence": 0.9},
            "skip me": {"expanded": "", "source": "override"},
        }
    )
    assert "a b" in entries
    assert "skip me" not in entries
    assert entries["a b"].confidence == 0.9


@pytest.mark.unit
def test_explicit_zero_confidence_is_preserved() -> None:
    # Regression: ``value or 1.0`` silently upgraded an explicit 0 to 1.0.
    entries = entries_from_phrase_dict(
        {"a b": {"expanded": "alpha", "source": "override", "confidence": 0}}
    )
    assert entries["a b"].confidence == 0.0
