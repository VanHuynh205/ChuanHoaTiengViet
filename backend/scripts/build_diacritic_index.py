"""Build a word-level diacritic mapping from one or more DataDauCau CSV files.

Usage::

    python scripts/build_diacritic_index.py \\
        --input data/DataDauCau/ViDiacritics_train.csv data/DataDauCau/ViDiacritics_val.csv \\
        --output data/diacritic/word_map.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

try:
    from scripts.diacritic_corpus import clean_token, iter_diacritic_pairs
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from diacritic_corpus import clean_token, iter_diacritic_pairs


def _as_paths(input_paths: Path | Iterable[Path]) -> list[Path]:
    if isinstance(input_paths, Path):
        return [input_paths]
    return list(input_paths)


def build_word_map(
    input_paths: Path | Iterable[Path],
    min_freq: int = 2,
    max_entries_per_word: int = 5,
) -> dict[str, list[str]]:
    pair_counts: dict[str, Counter[str]] = defaultdict(Counter)
    rows_processed = 0

    for no_diacritics, with_diacritics in iter_diacritic_pairs(_as_paths(input_paths)):
        nd_tokens = no_diacritics.split()
        wd_tokens = with_diacritics.split()

        if len(nd_tokens) != len(wd_tokens):
            continue

        for nd_tok, wd_tok in zip(nd_tokens, wd_tokens):
            nd_clean = clean_token(nd_tok)
            wd_clean = clean_token(wd_tok)
            if not nd_clean or not wd_clean:
                continue
            pair_counts[nd_clean][wd_clean] += 1

        rows_processed += 1
        if rows_processed % 500_000 == 0:
            print(f"  processed {rows_processed:,} aligned rows...", file=sys.stderr)

    word_map: dict[str, list[str]] = {}
    for nd_word, counter in sorted(pair_counts.items()):
        candidates = [
            (form, count)
            for form, count in counter.most_common(max_entries_per_word * 2)
            if count >= min_freq
        ]
        if not candidates:
            top = counter.most_common(1)
            if top:
                candidates = [top[0]]

        if not candidates:
            continue

        forms = [form for form, _ in candidates[:max_entries_per_word]]
        if forms and forms[0] != nd_word:
            word_map[nd_word] = forms

    return word_map


def main() -> None:
    parser = argparse.ArgumentParser(description="Build diacritic word map from DataDauCau")
    parser.add_argument(
        "--input",
        nargs="+",
        type=Path,
        required=True,
        help="One or more CSV paths (e.g. ViDiacritics_train.csv ViDiacritics_val.csv)",
    )
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--min-freq", type=int, default=2, help="Min frequency to include")
    parser.add_argument(
        "--max-entries-per-word",
        type=int,
        default=5,
        help="Maximum candidate forms retained per no-diacritic word",
    )
    args = parser.parse_args()

    missing = [path for path in args.input if not path.exists()]
    if missing:
        print(f"Error: input file not found: {missing[0]}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    inputs = ", ".join(str(path) for path in args.input)
    print(f"Building diacritic word map from {inputs}...", file=sys.stderr)
    started = time.perf_counter()

    word_map = build_word_map(
        args.input,
        min_freq=args.min_freq,
        max_entries_per_word=args.max_entries_per_word,
    )

    elapsed = time.perf_counter() - started
    print(f"Done: {len(word_map):,} entries in {elapsed:.1f}s", file=sys.stderr)

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(word_map, handle, ensure_ascii=False, indent=2)

    print(f"Written to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
