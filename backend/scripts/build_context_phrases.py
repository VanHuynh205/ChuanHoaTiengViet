#!/usr/bin/env python3
"""Build a context phrase diacritic map from DataDauCau CSV files.

Extracts n-gram pairs (2-4 tokens) where the no-diacritic form is ambiguous
(multiple tokens could map to different diacritized forms) but the corpus
consistently resolves them to the same diacritized phrase.

This replaces the need for hand-coded _CONTEXT_PHRASE_OVERRIDES and reduces
AI calls by letting rule-based restoration handle common phrases.

Usage::

    python scripts/build_context_phrases.py \\
        --input data/DataDauCau/ViDiacritics_train.csv data/DataDauCau/ViDiacritics_val.csv \\
        --output data/diacritic/context_phrases.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

try:
    from scripts.diacritic_corpus import clean_token, iter_diacritic_pairs
except ModuleNotFoundError:
    from diacritic_corpus import clean_token, iter_diacritic_pairs


def build_context_phrases(
    input_paths: list[Path],
    min_freq: int = 50,
    min_dominance: float = 0.85,
    ngram_sizes: tuple[int, ...] = (2, 3, 4),
    max_entries: int = 5000,
) -> dict[str, str]:
    """Build a map of no-diacritic n-grams to their dominant diacritized form.

    Parameters
    ----------
    input_paths:
        CSV files with ``no_diacritics`` and ``with_diacritics`` columns.
    min_freq:
        Minimum number of times an n-gram must appear in the corpus.
    min_dominance:
        The top diacritized form must account for at least this fraction
        of all occurrences to be included (ensures unambiguous resolution).
    ngram_sizes:
        Tuple of n-gram lengths to extract (e.g. 2, 3, 4).
    max_entries:
        Maximum number of context phrases to keep (top by frequency).

    Returns
    -------
    dict mapping ``"no_diac_token1 no_diac_token2 ..."`` to
    ``"diac_token1 diac_token2 ..."``.
    """
    ngram_counts: dict[str, Counter[str]] = defaultdict(Counter)
    rows_processed = 0

    def _iter_pairs_safe(paths: list[Path]):
        """Wrap iter_diacritic_pairs to handle OS read errors on large CSV."""
        try:
            yield from iter_diacritic_pairs(paths)
        except OSError as exc:
            print(f"  [WARN] CSV read stopped at row ~{rows_processed}: {exc}", file=sys.stderr)

    for no_diacritics, with_diacritics in _iter_pairs_safe(input_paths):
        nd_tokens = no_diacritics.split()
        wd_tokens = with_diacritics.split()

        if len(nd_tokens) != len(wd_tokens):
            continue

        nd_cleaned = [clean_token(t) for t in nd_tokens]
        wd_cleaned = [clean_token(t) for t in wd_tokens]

        for n in ngram_sizes:
            for i in range(len(nd_cleaned) - n + 1):
                nd_ngram = nd_cleaned[i : i + n]
                wd_ngram = wd_cleaned[i : i + n]

                if not all(nd_ngram) or not all(wd_ngram):
                    continue

                nd_key = " ".join(nd_ngram)
                wd_key = " ".join(wd_ngram)

                if nd_key == wd_key:
                    continue

                ngram_counts[nd_key][wd_key] += 1

        rows_processed += 1
        if rows_processed % 500_000 == 0:
            print(f"  processed {rows_processed:,} rows...", file=sys.stderr)

    context_phrases: list[tuple[str, str, int]] = []

    for nd_key, counter in ngram_counts.items():
        total = sum(counter.values())
        if total < min_freq:
            continue

        top_form, top_count = counter.most_common(1)[0]
        dominance = top_count / total

        if dominance < min_dominance:
            continue

        if nd_key == top_form:
            continue

        # Only multi-word phrases (single words handled by word_map)
        if " " not in nd_key:
            continue

        context_phrases.append((nd_key, top_form, top_count))

    context_phrases.sort(key=lambda x: x[2], reverse=True)
    context_phrases = context_phrases[:max_entries]

    result = {}
    for nd_key, wd_form, _count in sorted(context_phrases, key=lambda x: x[0]):
        result[nd_key] = wd_form

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build context phrase diacritic map from DataDauCau corpus"
    )
    parser.add_argument(
        "--input",
        nargs="+",
        type=Path,
        default=[
            Path("data/DataDauCau/ViDiacritics_train.csv"),
            Path("data/DataDauCau/ViDiacritics_val.csv"),
        ],
        help="CSV files to process",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/diacritic/context_phrases.json"),
        help="Output JSON path",
    )
    parser.add_argument(
        "--min-freq",
        type=int,
        default=50,
        help="Minimum n-gram frequency to include (default: 50)",
    )
    parser.add_argument(
        "--min-dominance",
        type=float,
        default=0.85,
        help="Minimum dominance ratio for top form (default: 0.85)",
    )
    parser.add_argument(
        "--max-entries",
        type=int,
        default=5000,
        help="Maximum entries to keep (default: 5000)",
    )
    args = parser.parse_args(argv)

    missing = [p for p in args.input if not p.exists()]
    if missing:
        print(f"Error: input file not found: {missing[0]}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(
        f"Building context phrase map (min_freq={args.min_freq}, "
        f"min_dominance={args.min_dominance})...",
        file=sys.stderr,
    )
    started = time.perf_counter()

    phrases = build_context_phrases(
        input_paths=args.input,
        min_freq=args.min_freq,
        min_dominance=args.min_dominance,
        max_entries=args.max_entries,
    )

    elapsed = time.perf_counter() - started
    print(f"Done: {len(phrases):,} context phrases in {elapsed:.1f}s", file=sys.stderr)

    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(phrases, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    print(f"Written to {args.output}", file=sys.stderr)

    by_length = defaultdict(int)
    for key in phrases:
        by_length[len(key.split())] += 1
    for n in sorted(by_length):
        print(f"  {n}-grams: {by_length[n]:,}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
