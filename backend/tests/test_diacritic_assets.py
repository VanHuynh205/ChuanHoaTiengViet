from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.build_bigram_index import build_bigram_index
from scripts.build_diacritic_assets import build_assets, main as build_assets_main
from scripts.build_diacritic_index import build_word_map
from scripts.diacritic_corpus import build_few_shot_examples, iter_diacritic_pairs
from scripts.eval_diacritic import evaluate_rule_only


def _write_csv(path: Path, rows: list[tuple[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["no_diacritics", "with_diacritics"])
        writer.writerows(rows)
    return path


@pytest.mark.unit
def test_iter_diacritic_pairs_requires_expected_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("source,target\nx,y\n", encoding="utf-8")

    with pytest.raises(ValueError):
        list(iter_diacritic_pairs([path]))


@pytest.mark.unit
def test_build_word_map_combines_multiple_csv_files(tmp_path: Path) -> None:
    first = _write_csv(
        tmp_path / "a.csv",
        [
            ("toi di hoc", "t\u00f4i \u0111i h\u1ecdc"),
            ("toi di hoc", "t\u00f4i \u0111i h\u1ecdc"),
        ],
    )
    second = _write_csv(
        tmp_path / "b.csv",
        [("hom nay", "h\u00f4m nay")],
    )

    word_map = build_word_map([first, second], min_freq=1)

    assert word_map["toi"] == ["t\u00f4i"]
    assert word_map["di"] == ["\u0111i"]
    assert word_map["hoc"] == ["h\u1ecdc"]
    assert word_map["hom"] == ["h\u00f4m"]


@pytest.mark.unit
def test_build_bigram_index_combines_multiple_csv_files(tmp_path: Path) -> None:
    first = _write_csv(tmp_path / "a.csv", [("toi di hoc", "t\u00f4i \u0111i h\u1ecdc")])
    second = _write_csv(tmp_path / "b.csv", [("toi di lam", "t\u00f4i \u0111i l\u00e0m")])

    index = build_bigram_index([first, second], min_freq=1, top_n=10)

    assert index["t\u00f4i_\u0111i"] == 2
    assert index["\u0111i_h\u1ecdc"] == 1
    assert index["\u0111i_l\u00e0m"] == 1


@pytest.mark.unit
def test_build_few_shot_examples_selects_short_unique_rows(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path / "data.csv",
        [
            ("toi di hoc", "t\u00f4i \u0111i h\u1ecdc"),
            ("toi di hoc", "t\u00f4i \u0111i h\u1ecdc"),
            ("hom nay", "h\u00f4m nay"),
        ],
    )

    examples = build_few_shot_examples([path], count=2)

    assert examples == [
        {"no_diacritics": "toi di hoc", "with_diacritics": "t\u00f4i \u0111i h\u1ecdc"},
        {"no_diacritics": "hom nay", "with_diacritics": "h\u00f4m nay"},
    ]


@pytest.mark.unit
def test_build_assets_writes_runtime_files(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path / "data.csv",
        [
            ("toi di hoc", "t\u00f4i \u0111i h\u1ecdc"),
            ("toi di lam", "t\u00f4i \u0111i l\u00e0m"),
        ],
    )
    output_dir = tmp_path / "diacritic"

    manifest = build_assets(
        input_paths=[path],
        output_dir=output_dir,
        min_freq=1,
        bigram_top_n=10,
        few_shot_count=1,
    )

    assert manifest["word_map_entries"] >= 3
    assert manifest["bigram_entries"] >= 2
    assert json.loads((output_dir / "word_map.json").read_text(encoding="utf-8"))["toi"] == [
        "t\u00f4i"
    ]
    assert len(json.loads((output_dir / "sample_few_shot.json").read_text(encoding="utf-8"))) == 1
    assert (output_dir / "diacritic_assets_manifest.json").exists()


@pytest.mark.unit
def test_build_assets_main_returns_two_for_missing_input(tmp_path: Path) -> None:
    rc = build_assets_main(["--input", str(tmp_path / "missing.csv")])
    assert rc == 2


@pytest.mark.unit
def test_evaluate_rule_only_uses_bigram_context() -> None:
    samples = [("nghe thuat", "ngh\u1ec7 thu\u1eadt")]
    word_map = {"nghe": ["nghe", "ngh\u1ec7"], "thuat": ["thu\u1eadt"]}
    bigram_freq = {"ngh\u1ec7_thu\u1eadt": 7}

    result = evaluate_rule_only(samples, word_map, bigram_freq)

    assert result["token_accuracy"] == 1.0
    assert result["sentence_exact"] == 1.0
