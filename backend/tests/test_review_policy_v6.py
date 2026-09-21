"""Regression tests for review_policy v6 behavior.

Covers two fixes found while diagnosing why AI verification could not rescue
dense unaccented chat text (Test2):

1. The "never strip diacritics" guard used to block legitimate repairs of a
   WRONG tone added by the rule restorer itself ("nghề" -> "nghe") even though
   the bare form is one of the restorer's own declared candidates.
2. The contextual-edit budget used to revert the WHOLE chunk once exceeded,
   discarding every good fix in that chunk (all-or-nothing). It now keeps the
   edits that fit the budget, in text order, and serves the baseline for the
   overflow.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai.review_policy import accept_edits  # noqa: E402

NGHE_CANDIDATES = ["nghệ", "nghề", "nghe", "nghé", "nghè", "nghê", "nghễ", "nghẹ"]


def test_strip_to_declared_candidate_is_allowed():
    """The restorer added a wrong tone; AI picks the bare declared candidate."""
    accepted, changes, rejected = accept_edits(
        "chuyện nghề thì đơn giản",
        "chuyện nghe thì đơn giản",
        confidence=0.9,
        threshold=0.7,
        diacritic_candidates={"nghe": NGHE_CANDIDATES},
    )
    assert accepted == "chuyện nghe thì đơn giản"
    assert changes == [("nghề", "nghe")]
    assert rejected == 0


def test_strip_to_undeclared_form_is_still_rejected():
    """Without the bare form among the declared candidates, stripping stays blocked."""
    source = "sống khô khăn mà"
    accepted, changes, rejected = accept_edits(
        source,
        "sống khô khan mà",
        confidence=0.95,
        threshold=0.7,
        diacritic_candidates={"khan": ["khăn", "khán", "khẩn"]},
    )
    assert accepted == source
    assert changes == []
    assert rejected == 1


def test_over_budget_chunk_keeps_first_edits_instead_of_reverting_all():
    # Base-letter edits (fold changes) consume the contextual budget: 30 x
    # cost 1, budget = min(24, max(4, int(30*0.12))) = 4. Tone-only edits are
    # budget-free by design, so base-changing tokens are used here.
    source = " ".join(["dc"] * 30)
    proposed = " ".join(["được"] * 30)

    accepted, changes, rejected = accept_edits(
        source, proposed, confidence=0.9, threshold=0.7
    )

    assert len(changes) == 4
    assert accepted.split()[:4] == ["được"] * 4
    # The overflow keeps the baseline instead of reverting everything.
    assert accepted.split()[4] == "dc"
    assert rejected == 26


def test_under_budget_chunk_still_applies_every_edit():
    accepted, changes, rejected = accept_edits(
        "co mot nam", "cố một năm", confidence=0.9, threshold=0.7
    )
    assert accepted == "cố một năm"
    assert len(changes) == 3
    assert rejected == 0


def test_abbreviation_edits_do_not_consume_the_contextual_budget():
    accepted, changes, rejected = accept_edits(
        "ko hoc bai",
        "không học bài",
        confidence=0.9,
        threshold=0.7,
        abbreviations={"ko": ["không"]},
    )
    assert accepted == "không học bài"
    assert len(changes) == 3
    assert rejected == 0


@pytest.mark.parametrize(
    "source,proposed",
    [
        ("Sống tử tế nghe có vẻ.", "Song tu te nghe co ve."),
        ("Tôi đi học.", "toi đi học."),
    ],
)
def test_full_strip_without_candidates_still_rejected(source, proposed):
    accepted, changes, _ = accept_edits(
        source, proposed, confidence=0.97, threshold=0.7
    )
    assert accepted == source
    assert changes == []
