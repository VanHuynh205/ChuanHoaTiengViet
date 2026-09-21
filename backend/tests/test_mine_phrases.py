"""Tests for scripts.mine_phrases."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.mine_phrases import (
    iter_pairs,
    main,
    mine,
    ngrams,
    tokenize,
)


def _write_csv(tmp_path: Path, rows: list[tuple[str, str]]) -> Path:
    path = tmp_path / "mini.csv"
    lines = ["no_diacritics,with_diacritics"]
    for a, b in rows:
        lines.append(f'"{a}","{b}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.mark.unit
def test_tokenize_lowercases_and_splits_on_punctuation() -> None:
    assert tokenize("Hôm Nay, Đi Học!") == ["hôm", "nay", "đi", "học"]


@pytest.mark.unit
def test_ngrams_of_short_input_is_empty() -> None:
    assert list(ngrams(["a"], 2)) == []


@pytest.mark.unit
def test_ngrams_yields_overlapping_windows() -> None:
    assert list(ngrams(["a", "b", "c"], 2)) == [("a", "b"), ("b", "c")]


@pytest.mark.unit
def test_iter_pairs_rejects_unexpected_header(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        list(iter_pairs(bad))


@pytest.mark.unit
def test_mine_finds_repeated_bigram(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        [
            ("hom nay", "hôm nay"),
            ("hom nay", "hôm nay"),
            ("hom nay", "hôm nay"),
            ("xin chao", "xin chào"),
        ],
    )
    report = mine(csv_path, min_freq=2, max_ngram=3, top_n=10)
    phrases = {p["phrase"] for p in report["phrases"]}
    assert "hôm nay" in phrases
    assert all(p["freq"] >= 2 for p in report["phrases"])


@pytest.mark.unit
def test_mine_respects_top_n_cap(tmp_path: Path) -> None:
    # Use alphabetic-only tokens because mine() drops digits during tokenisation.
    pairs: list[tuple[str, str]] = []
    for i in range(20):
        token_a = "alpha" + chr(ord("a") + (i % 26))
        token_b = "beta" + chr(ord("a") + (i % 26))
        if i >= 26:
            token_a += "x"
            token_b += "x"
        pair_text = f"{token_a} {token_b}"
        pairs.extend([(pair_text, pair_text)] * 3)
    csv_path = _write_csv(tmp_path, pairs)
    report = mine(csv_path, min_freq=2, max_ngram=2, top_n=5)
    assert len(report["phrases"]) == 5


@pytest.mark.unit
def test_mine_rejects_max_ngram_below_two(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path, [("a b", "a b")])
    with pytest.raises(ValueError):
        mine(csv_path, min_freq=1, max_ngram=1)


@pytest.mark.unit
def test_main_writes_json_and_returns_zero(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        [("foo bar", "foo bar"), ("foo bar", "foo bar"), ("foo bar", "foo bar")],
    )
    output = tmp_path / "out.json"
    rc = main(
        [
            "--input",
            str(csv_path),
            "--output",
            str(output),
            "--min-freq",
            "2",
            "--max-ngram",
            "2",
        ]
    )
    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert "generated_at" in payload
    assert payload["min_freq"] == 2
    assert {p["phrase"] for p in payload["phrases"]} == {"foo bar"}


@pytest.mark.unit
def test_main_returns_two_when_input_missing(tmp_path: Path) -> None:
    rc = main(["--input", str(tmp_path / "missing.csv")])
    assert rc == 2


@pytest.mark.slow
def test_sample_5k_runs_under_30_seconds(tmp_path: Path) -> None:
    """Acceptance criterion §5.8: mining sample_5k.csv must finish in <30s."""
    src = Path("data/DataDauCau/sample_5k.csv")
    if not src.exists():
        pytest.skip("sample_5k.csv not present in this checkout")
    output = tmp_path / "mined.json"
    rc = main(
        [
            "--input",
            str(src),
            "--output",
            str(output),
            "--min-freq",
            "5",
            "--max-ngram",
            "4",
            "--top-n",
            "1000",
        ]
    )
    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["elapsed_seconds"] < 30
    assert payload["rows_seen"] >= 4_900
