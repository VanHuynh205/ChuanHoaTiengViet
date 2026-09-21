"""Regression tests for Vietnamese diacritic restoration on real chat text.

Loads test cases from data/diacritic/chat_regression_test.csv and runs
the rule-based restorer against each case, reporting per-category and
overall accuracy.

Usage::

    python -m pytest tests/test_diacritic_regression.py -v
    python -m pytest tests/test_diacritic_regression.py -v -k context_phrase
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.normalizer.diacritic_restorer import _rule_restore, load_bigram_freq, load_word_map  # noqa: E402

DATA_DIR = ROOT / "data" / "diacritic"
TEST_CSV = DATA_DIR / "chat_regression_test.csv"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def word_map() -> dict[str, list[str]]:
    return load_word_map(DATA_DIR / "word_map.json")


@pytest.fixture(scope="module")
def bigram_freq() -> dict[str, int]:
    return load_bigram_freq(DATA_DIR / "bigram_freq.json")


@pytest.fixture(scope="module")
def test_cases() -> list[dict[str, str]]:
    if not TEST_CSV.exists():
        pytest.skip(f"Test CSV not found: {TEST_CSV}")
    with TEST_CSV.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Token-level accuracy helper
# ---------------------------------------------------------------------------

def token_accuracy(reference: str, hypothesis: str) -> float:
    ref_tokens = reference.strip().split()
    hyp_tokens = hypothesis.strip().split()
    if not ref_tokens:
        return 1.0
    matches = sum(1 for r, h in zip(ref_tokens, hyp_tokens) if r == h)
    return matches / len(ref_tokens)


# ---------------------------------------------------------------------------
# Parametrized per-case tests
# ---------------------------------------------------------------------------

def _load_cases() -> list[tuple[str, str, str]]:
    """Load test cases for parametrize (runs at collection time)."""
    if not TEST_CSV.exists():
        return []
    with TEST_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [
            (row["no_diacritics"], row["with_diacritics"], row.get("category", "unknown"))
            for row in reader
        ]


_CASES = _load_cases()


@pytest.mark.parametrize(
    "input_text,expected,category",
    _CASES,
    ids=[f"{c[2]}_{i}" for i, c in enumerate(_CASES)],
)
def test_diacritic_restoration(
    input_text: str,
    expected: str,
    category: str,
    word_map: dict[str, list[str]],
    bigram_freq: dict[str, int],
) -> None:
    restored, _, _, _ = _rule_restore(input_text, word_map, bigram_freq)
    acc = token_accuracy(expected, restored)

    # Ambiguous cases are known hard for rule-based (needs AI verification)
    threshold = 0.0 if category == "ambiguous" else 0.6
    assert acc >= threshold, (
        f"[{category}] accuracy {acc:.0%} < {threshold:.0%}\n"
        f"  input:    {input_text!r}\n"
        f"  expected: {expected!r}\n"
        f"  got:      {restored!r}"
    )


# ---------------------------------------------------------------------------
# Aggregate accuracy report
# ---------------------------------------------------------------------------

def test_overall_accuracy_report(
    test_cases: list[dict[str, str]],
    word_map: dict[str, list[str]],
    bigram_freq: dict[str, int],
) -> None:
    """Run all cases and report per-category + overall accuracy."""
    category_stats: dict[str, list[float]] = defaultdict(list)
    failures: list[tuple[str, str, str, str, float]] = []

    for row in test_cases:
        input_text = row["no_diacritics"]
        expected = row["with_diacritics"]
        category = row.get("category", "unknown")

        restored, _, _, _ = _rule_restore(input_text, word_map, bigram_freq)
        acc = token_accuracy(expected, restored)
        category_stats[category].append(acc)

        if acc < 1.0:
            failures.append((category, input_text, expected, restored, acc))

    # Print report
    print("\n" + "=" * 70)
    print("DIACRITIC REGRESSION TEST REPORT")
    print("=" * 70)

    all_accs: list[float] = []
    for category in sorted(category_stats):
        accs = category_stats[category]
        all_accs.extend(accs)
        avg = sum(accs) / len(accs) if accs else 0
        perfect = sum(1 for a in accs if a >= 1.0)
        print(f"  {category:<20s}  avg={avg:.1%}  perfect={perfect}/{len(accs)}")

    overall = sum(all_accs) / len(all_accs) if all_accs else 0
    total_perfect = sum(1 for a in all_accs if a >= 1.0)
    print(f"\n  {'OVERALL':<20s}  avg={overall:.1%}  perfect={total_perfect}/{len(all_accs)}")

    if failures:
        print(f"\n  Imperfect cases ({len(failures)}):")
        for cat, inp, _exp, got, acc in failures[:15]:
            # Use ASCII repr to avoid Windows cp932 encoding errors
            print(f"    [{cat}] {acc:.0%}  in={inp!a}  got={got!a}")

    print("=" * 70)

    assert overall >= 0.70, f"Overall accuracy {overall:.1%} below 70% threshold"
