#!/usr/bin/env python3
"""Build all runtime diacritic assets from DataDauCau CSV files."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.build_bigram_index import build_bigram_index
    from scripts.build_diacritic_index import build_word_map
    from scripts.diacritic_corpus import build_few_shot_examples
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from build_bigram_index import build_bigram_index
    from build_diacritic_index import build_word_map
    from diacritic_corpus import build_few_shot_examples

DEFAULT_INPUTS = (
    Path("data/DataDauCau/ViDiacritics_train.csv"),
    Path("data/DataDauCau/ViDiacritics_val.csv"),
)
DEFAULT_TEST_INPUT = Path("data/DataDauCau/ViDiacritics_test.csv")


def build_assets(
    input_paths: list[Path],
    output_dir: Path,
    min_freq: int = 2,
    max_entries_per_word: int = 5,
    bigram_top_n: int = 100_000,
    few_shot_count: int = 16,
) -> dict:
    started = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)

    word_map = build_word_map(
        input_paths,
        min_freq=min_freq,
        max_entries_per_word=max_entries_per_word,
    )
    bigram_freq = build_bigram_index(
        input_paths,
        min_freq=min_freq,
        top_n=bigram_top_n,
    )
    few_shot = build_few_shot_examples(input_paths, count=few_shot_count)

    word_map_path = output_dir / "word_map.json"
    bigram_path = output_dir / "bigram_freq.json"
    few_shot_path = output_dir / "sample_few_shot.json"
    manifest_path = output_dir / "diacritic_assets_manifest.json"

    _write_json(word_map_path, word_map)
    _write_json(bigram_path, bigram_freq)
    _write_json(few_shot_path, few_shot)

    elapsed = round(time.perf_counter() - started, 2)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": [str(path) for path in input_paths],
        "min_freq": min_freq,
        "max_entries_per_word": max_entries_per_word,
        "bigram_top_n": bigram_top_n,
        "few_shot_count": few_shot_count,
        "word_map_entries": len(word_map),
        "bigram_entries": len(bigram_freq),
        "few_shot_entries": len(few_shot),
        "elapsed_seconds": elapsed,
        "outputs": {
            "word_map": str(word_map_path),
            "bigram_freq": str(bigram_path),
            "sample_few_shot": str(few_shot_path),
        },
    }
    _write_json(manifest_path, manifest)
    return manifest


def _write_json(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            payload, handle, ensure_ascii=False, indent=2, sort_keys=isinstance(payload, dict)
        )
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build diacritic runtime assets")
    parser.add_argument(
        "--input",
        nargs="+",
        type=Path,
        default=list(DEFAULT_INPUTS),
        help="CSV files to combine. Defaults to train + validation.",
    )
    parser.add_argument(
        "--include-test",
        action="store_true",
        help="Also include ViDiacritics_test.csv in runtime assets.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/diacritic"),
        help="Directory for word_map.json, bigram_freq.json and sample_few_shot.json.",
    )
    parser.add_argument("--min-freq", type=int, default=2)
    parser.add_argument("--max-entries-per-word", type=int, default=5)
    parser.add_argument("--bigram-top-n", type=int, default=100_000)
    parser.add_argument("--few-shot-count", type=int, default=16)
    args = parser.parse_args(argv)

    input_paths = list(args.input)
    if args.include_test and DEFAULT_TEST_INPUT not in input_paths:
        input_paths.append(DEFAULT_TEST_INPUT)

    missing = [path for path in input_paths if not path.exists()]
    if missing:
        print(f"Error: input file not found: {missing[0]}", file=sys.stderr)
        return 2

    manifest = build_assets(
        input_paths=input_paths,
        output_dir=args.output_dir,
        min_freq=args.min_freq,
        max_entries_per_word=args.max_entries_per_word,
        bigram_top_n=args.bigram_top_n,
        few_shot_count=args.few_shot_count,
    )
    print(json.dumps(manifest, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
