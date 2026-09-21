"""Independent regression cases for the diacritic-overwrite bug.

The core guard lives in ``diacritic_restorer._context_phrase_overrides``
(a folded phrase match may only repair *missing* accents, never overwrite
tokens the user already typed with diacritics). ``tests/test_context_phrase_guard.py``
covers the basic NFC cases; this file locks the remaining edge cases:

* NFD (decomposed) input must be detected as accented and preserved verbatim.
* A 3-token phrase must keep a valid alternate spelling inside its span
  ("mo khoá may" → "mở khoá máy", not "mở khóa máy").
* "đ" does not decompose under NFD but is still an intended accent, so a
  span covering "đang" must not expand it to "đăng".
* The phrase index itself (``phrase_index`` / ``phrase_normalizer``) must
  never fold diacritics while matching — matching stays exact-lowercase.
"""

from __future__ import annotations

import tempfile
import unicodedata
from pathlib import Path

import pytest

from app.config import Settings
from app.normalizer.diacritic_restorer import (
    SyncDiacriticRestorer,
    _context_phrase_overrides,
)
from app.normalizer.phrase_index import PhraseEntry, PhraseIndex
from app.normalizer.phrase_normalizer import PhraseNormalizer


def _nfd(text: str) -> str:
    return unicodedata.normalize("NFD", text)


def _restore(
    text: str,
    phrases: dict[tuple[str, ...], tuple[str, ...]],
    word_map: dict[str, list[str]] | None = None,
) -> str:
    restorer = SyncDiacriticRestorer(
        word_map=word_map or {},
        bigram_freq={},
        context_phrases=phrases,
        min_text_length=1,
        detection_threshold=0.0,
    )
    return restorer.restore(text).restored_text


# ---------------------------------------------------------------------------
# Diacritic restorer: folded phrase matches must not rewrite accented tokens
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_nfd_decomposed_input_keeps_user_accent() -> None:
    """NFD "kiên" carries Mn marks, so the guard must keep it verbatim."""
    phrases = {("su", "kien"): ("sự", "kiện")}
    text = _nfd("su kiên nhẫn")
    restored = _restore(text, phrases)

    assert _nfd("kiên") in restored.split()
    assert restored == "sự " + _nfd("kiên") + " " + _nfd("nhẫn")


@pytest.mark.unit
def test_three_token_phrase_keeps_valid_alternate_spelling() -> None:
    """"khoá" and "khóa" are both valid; the phrase must not re-spell it."""
    phrases = {("mo", "khoa", "may"): ("mở", "khóa", "máy")}
    assert _restore("mo khoá may", phrases) == "mở khoá máy"


@pytest.mark.unit
def test_d_digraph_token_is_not_expanded_by_phrase() -> None:
    """Span ("đang", "ky"): "đang" is intentional (đ), only "ky" is repaired."""
    phrases = {("dang", "ky"): ("đăng", "ký")}
    word_map = {"mon": ["môn"], "hoc": ["học"]}
    restored = _restore("đang ky mon hoc", phrases, word_map)
    assert restored == "đang ký môn học"


@pytest.mark.unit
def test_override_writer_skips_d_digraph_position() -> None:
    phrases = {("dang", "ky"): ("đăng", "ký")}
    overrides = _context_phrase_overrides(["đang", "ky"], phrases)
    assert overrides == {1: "ký"}


# ---------------------------------------------------------------------------
# Phrase index / phrase normalizer: matching never folds diacritics
# ---------------------------------------------------------------------------


class _FakePendingService:
    def submit_pending_abbreviation(self, **kwargs):
        return {"abbr": kwargs["abbr"], "status": "PENDING_CREATED"}


def _override_index(overrides: dict[str, str]) -> PhraseIndex:
    return PhraseIndex.build(
        overrides={
            phrase: PhraseEntry(expanded=expanded, source="override", confidence=1.0)
            for phrase, expanded in overrides.items()
        },
        max_ngram=5,
    )


@pytest.mark.unit
def test_phrase_index_scan_does_not_fold_accents() -> None:
    """A folded key must not match accented input (accent-loss guard)."""
    index = _override_index({"su kien": "sự kiện", "đk hp": "đăng ký học phần"})

    assert index.scan([(0, "su"), (1, "kiên")]) == []
    # "đ" must not fold to "d" during scanning either.
    assert index.scan([(0, "dk"), (1, "hp")]) == []


@pytest.mark.unit
def test_phrase_index_still_matches_exact_tokens() -> None:
    """Exact lowercase matching (including "đ") keeps the core feature."""
    index = _override_index({"su kien": "sự kiện", "đk hp": "đăng ký học phần"})

    spans = index.scan([(0, "su"), (1, "kien")])
    assert len(spans) == 1
    assert spans[0].expanded == "sự kiện"

    spans = index.scan([(0, "đk"), (1, "hp")])
    assert len(spans) == 1
    assert spans[0].expanded == "đăng ký học phần"


@pytest.mark.unit
def test_phrase_normalizer_never_rewrites_accented_span() -> None:
    """End-to-end: an unaccented phrase key cannot consume accented tokens."""
    settings = Settings(data_dir=Path(tempfile.mkdtemp()))
    normalizer = PhraseNormalizer(settings, _FakePendingService())
    index = _override_index({"su kien": "sự kiện"})

    result = normalizer.normalize_phrases(
        "su kiên nhẫn",
        index,
        known_words={"kiên", "nhẫn"},
        approved_abbreviations={},
    )

    assert result.phrase_matches == []
    assert result.consumed_token_indices == set()
    assert result.tokens == ["su", "kiên", "nhẫn"]
