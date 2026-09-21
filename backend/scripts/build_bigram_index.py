#!/usr/bin/env python3
"""Build a bigram frequency index from one or more DataDauCau CSV files.

Scans the ``with_diacritics`` column and counts consecutive word-pair
occurrences. Outputs a JSON file mapping ``"word1_word2"`` to frequency.

Usage::

    python scripts/build_bigram_index.py \\
        --input data/DataDauCau/ViDiacritics_train.csv data/DataDauCau/ViDiacritics_val.csv \\
        --output data/diacritic/bigram_freq.json \\
        --min-freq 2 --top-n 100000
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

try:
    from scripts.diacritic_corpus import iter_diacritic_pairs, tokenize_words
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from diacritic_corpus import iter_diacritic_pairs, tokenize_words


def _as_paths(input_paths: Path | Iterable[Path]) -> list[Path]:
    if isinstance(input_paths, Path):
        return [input_paths]
    return list(input_paths)


def extract_bigrams(text: str) -> list[tuple[str, str]]:
    """Extract consecutive word bigrams from a sentence."""
    words = tokenize_words(text)
    return [(words[i], words[i + 1]) for i in range(len(words) - 1)]


def build_bigram_index(
    input_paths: Path | Iterable[Path],
    min_freq: int = 2,
    top_n: int = 10_000,
) -> dict[str, int]:
    """Build a bigram frequency map from CSV corpus files."""
    counter: Counter[str] = Counter()
    rows_processed = 0

    for _, with_diacritics in iter_diacritic_pairs(_as_paths(input_paths)):
        for w1, w2 in extract_bigrams(with_diacritics):
            counter[f"{w1}_{w2}"] += 1
        rows_processed += 1
        if rows_processed % 500_000 == 0:
            print(f"  processed {rows_processed:,} rows...", file=sys.stderr)

    return {key: count for key, count in counter.most_common(top_n) if count >= min_freq}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build bigram frequency index")
    parser.add_argument(
        "--input",
        nargs="+",
        type=Path,
        default=[Path("data/DataDauCau/sample_5k.csv")],
        help="One or more CSV files with no_diacritics and with_diacritics columns",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/diacritic/bigram_freq.json"),
        help="Output JSON file for bigram frequencies",
    )
    parser.add_argument("--min-freq", type=int, default=2, help="Minimum frequency")
    parser.add_argument("--top-n", type=int, default=10_000, help="Max bigrams to keep")
    parser.add_argument("--show-top", type=int, default=0, help="Print top N bigrams")
    args = parser.parse_args()

    missing = [path for path in args.input if not path.exists()]
    if missing:
        print(f"ERROR: Input file not found: {missing[0]}", file=sys.stderr)
        sys.exit(1)

    inputs = ", ".join(str(path) for path in args.input)
    print(f"Building bigram index from {inputs}...", file=sys.stderr)
    index = build_bigram_index(args.input, min_freq=args.min_freq, top_n=args.top_n)
    print(f"  Total bigrams with freq >= {args.min_freq}: {len(index)}", file=sys.stderr)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(index, handle, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"  Written to {args.output}", file=sys.stderr)
    if args.show_top:
        print(f"\nTop {args.show_top} bigrams:", file=sys.stderr)
        for key, count in sorted(index.items(), key=lambda item: -item[1])[: args.show_top]:
            print(f"  {key}: {count}", file=sys.stderr)


if __name__ == "__main__":
    main()
