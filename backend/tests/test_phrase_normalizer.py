"""Tests for app.normalizer.phrase_normalizer."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.config import Settings
from app.normalizer.phrase_index import PhraseEntry, PhraseIndex
from app.normalizer.phrase_normalizer import PhraseMatch, PhraseNormalizer


class FakePendingService:
    """Records pending submissions; never touches a DB."""

    def __init__(self) -> None:
        self.submissions: list[dict] = []

    def submit_pending_abbreviation(self, **kwargs):
        self.submissions.append(kwargs)
        return {
            "abbr": kwargs["abbr"],
            "status": "PENDING_CREATED",
            "pending_id": f"pending-{kwargs['abbr']}",
            "has_suggested": False,
        }


def _settings(**overrides) -> Settings:
    return Settings(data_dir=Path(tempfile.mkdtemp()), **overrides)


def _override_index(overrides: dict[str, str]) -> PhraseIndex:
    return PhraseIndex.build(
        overrides={
            phrase: PhraseEntry(expanded=expanded, source="override", confidence=1.0)
            for phrase, expanded in overrides.items()
        },
        max_ngram=5,
    )


@pytest.mark.unit
def test_phrase_match_overrides_token_expand() -> None:
    settings = _settings()
    pending = FakePendingService()
    normalizer = PhraseNormalizer(settings, pending)
    index = _override_index({"đk hp": "đăng ký học phần"})

    result = normalizer.normalize_phrases(
        "đk hp xong",
        index,
        known_words={"xong"},
        approved_abbreviations={},
    )

    assert len(result.phrase_matches) == 1
    match = result.phrase_matches[0]
    assert match == PhraseMatch(
        start_token=0,
        end_token=2,
        matched_phrase="đk hp",
        expanded="đăng ký học phần",
        confidence=1.0,
        source="override",
    )
    assert "PHRASE" in result.error_types
    assert result.token_replacements[0] == "đăng ký học phần"
    assert result.token_replacements[1] == ""
    assert 0 in result.consumed_token_indices
    assert 1 in result.consumed_token_indices


@pytest.mark.unit
def test_three_token_match() -> None:
    settings = _settings()
    pending = FakePendingService()
    normalizer = PhraseNormalizer(settings, pending)
    index = _override_index({"k pải v": "không phải vậy"})

    result = normalizer.normalize_phrases(
        "k pải v đâu",
        index,
        known_words={"đâu"},
        approved_abbreviations={},
    )

    assert len(result.phrase_matches) == 1
    assert result.phrase_matches[0].matched_phrase == "k pải v"
    assert result.phrase_matches[0].expanded == "không phải vậy"


@pytest.mark.unit
def test_empty_input_returns_empty_result() -> None:
    settings = _settings()
    normalizer = PhraseNormalizer(settings, FakePendingService())
    result = normalizer.normalize_phrases(
        "",
        _override_index({"đk hp": "đăng ký học phần"}),
        known_words=set(),
        approved_abbreviations={},
    )
    assert result.phrase_matches == []
    assert result.consumed_token_indices == set()


@pytest.mark.unit
def test_empty_index_with_strict_pending() -> None:
    settings = _settings()
    pending = FakePendingService()
    normalizer = PhraseNormalizer(settings, pending)
    result = normalizer.normalize_phrases(
        "abc xyz",
        PhraseIndex.empty(max_ngram=5),
        known_words={"xong"},
        approved_abbreviations={},
    )
    assert result.phrase_matches == []
    assert len(pending.submissions) == 1
    submitted = pending.submissions[0]
    assert submitted["abbr"] == "abc_xyz"
    assert submitted["source"] == "phrase_runtime"


@pytest.mark.unit
def test_strict_heuristic_skips_when_one_token_is_known() -> None:
    settings = _settings()
    pending = FakePendingService()
    normalizer = PhraseNormalizer(settings, pending)
    result = normalizer.normalize_phrases(
        "abc xong",
        PhraseIndex.empty(max_ngram=5),
        known_words={"xong"},
        approved_abbreviations={},
    )
    assert result.pending_phrase_submissions == []
    assert pending.submissions == []


@pytest.mark.unit
def test_strict_heuristic_skips_when_token_already_approved() -> None:
    settings = _settings()
    pending = FakePendingService()
    normalizer = PhraseNormalizer(settings, pending)
    result = normalizer.normalize_phrases(
        "ko zzz",
        PhraseIndex.empty(max_ngram=5),
        known_words=set(),
        approved_abbreviations={"ko": "không"},
    )
    assert result.pending_phrase_submissions == []


@pytest.mark.unit
def test_phrase_match_clears_consumed_run_so_no_pending() -> None:
    settings = _settings()
    pending = FakePendingService()
    normalizer = PhraseNormalizer(settings, pending)
    index = _override_index({"abc xyz": "alpha beta"})

    result = normalizer.normalize_phrases(
        "abc xyz",
        index,
        known_words=set(),
        approved_abbreviations={},
    )
    assert result.pending_phrase_submissions == []
    assert pending.submissions == []
    assert len(result.phrase_matches) == 1


@pytest.mark.unit
def test_pending_dedup_via_already_pending_set() -> None:
    settings = _settings()
    pending = FakePendingService()
    normalizer = PhraseNormalizer(settings, pending)
    seen: set[str] = set()
    for _ in range(2):
        normalizer.normalize_phrases(
            "abc xyz",
            PhraseIndex.empty(max_ngram=5),
            known_words=set(),
            approved_abbreviations={},
            already_pending=seen,
        )
    assert len(pending.submissions) == 1


@pytest.mark.unit
def test_phrase_max_ngram_caps_pending_run_length() -> None:
    settings = _settings(phrase_max_ngram=2)
    pending = FakePendingService()
    normalizer = PhraseNormalizer(settings, pending)
    normalizer.normalize_phrases(
        "abc xyz uvw",
        PhraseIndex.empty(max_ngram=5),
        known_words=set(),
        approved_abbreviations={},
    )
    assert pending.submissions[0]["abbr"] == "abc_xyz"


@pytest.mark.unit
def test_alpha_token_pairs_keeps_indices() -> None:
    pairs = PhraseNormalizer.alpha_token_pairs(["đk", ",", "hp"])
    assert pairs == [(0, "đk"), (2, "hp")]
