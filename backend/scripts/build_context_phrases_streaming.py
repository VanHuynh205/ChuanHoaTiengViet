#!/usr/bin/env python3
"""Memory-bounded context phrase builder for DataDauCau CSV files.

This builder trades a small amount of candidate-mining recall for predictable
RAM use on modest machines. It scans the corpus once to keep only high-frequency
candidate no-diacritic n-grams, then scans it again to count exact diacritized
variants for those candidates.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

try:
    from scripts.diacritic_corpus import clean_token, iter_diacritic_pairs
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from diacritic_corpus import clean_token, iter_diacritic_pairs


DEFAULT_INPUTS = [
    Path("data/DataDauCau/ViDiacritics_val.csv"),
]


def iter_context_pairs(
    input_paths: Iterable[Path],
    ngram_sizes: tuple[int, ...],
    max_rows: int | None = None,
) -> Iterable[tuple[str, str]]:
    rows_seen = 0
    for no_diacritics, with_diacritics in iter_diacritic_pairs(input_paths):
        if max_rows is not None and rows_seen >= max_rows:
            break

        rows_seen += 1
        nd_tokens = no_diacritics.split()
        wd_tokens = with_diacritics.split()
        if len(nd_tokens) != len(wd_tokens):
            continue

        nd_cleaned = [clean_token(token) for token in nd_tokens]
        wd_cleaned = [clean_token(token) for token in wd_tokens]

        for ngram_size in ngram_sizes:
            for index in range(len(nd_cleaned) - ngram_size + 1):
                nd_ngram = nd_cleaned[index : index + ngram_size]
                wd_ngram = wd_cleaned[index : index + ngram_size]
                if not all(nd_ngram) or not all(wd_ngram):
                    continue

                nd_key = " ".join(nd_ngram)
                wd_key = " ".join(wd_ngram)
                if nd_key != wd_key:
                    yield nd_key, wd_key


def mine_candidate_keys(
    input_paths: list[Path],
    ngram_sizes: tuple[int, ...],
    candidate_limit: int,
    prune_to: int,
    max_rows: int | None = None,
) -> set[str]:
    counts: Counter[str] = Counter()
    pairs_seen = 0

    for nd_key, _ in iter_context_pairs(input_paths, ngram_sizes, max_rows=max_rows):
        counts[nd_key] += 1
        pairs_seen += 1

        if pairs_seen % 1_000_000 == 0:
            print(
                f"  candidate pass: {pairs_seen:,} n-grams, "
                f"{len(counts):,} tracked",
                file=sys.stderr,
            )

        if len(counts) > candidate_limit:
            counts = Counter(dict(counts.most_common(prune_to)))
            print(
                f"  pruned candidates to {len(counts):,} tracked keys",
                file=sys.stderr,
            )

    return set(counts)


def count_candidate_variants(
    input_paths: list[Path],
    ngram_sizes: tuple[int, ...],
    candidates: set[str],
    max_rows: int | None = None,
) -> dict[str, Counter[str]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    pairs_seen = 0

    for nd_key, wd_key in iter_context_pairs(input_paths, ngram_sizes, max_rows=max_rows):
        pairs_seen += 1
        if nd_key not in candidates:
            continue

        counts[nd_key][wd_key] += 1
        if pairs_seen % 1_000_000 == 0:
            print(
                f"  exact pass: {pairs_seen:,} n-grams, "
                f"{len(counts):,} candidates matched",
                file=sys.stderr,
            )

    return counts


def select_context_phrases(
    variant_counts: dict[str, Counter[str]],
    min_freq: int,
    min_dominance: float,
    max_entries: int,
) -> dict[str, str]:
    selected: list[tuple[str, str, int]] = []

    for nd_key, counter in variant_counts.items():
        total = sum(counter.values())
        if total < min_freq:
            continue

        top_form, top_count = counter.most_common(1)[0]
        if top_count / total < min_dominance:
            continue
        if nd_key == top_form or " " not in nd_key:
            continue

        selected.append((nd_key, top_form, top_count))

    selected.sort(key=lambda item: item[2], reverse=True)
    selected = selected[:max_entries]
    return {nd_key: wd_form for nd_key, wd_form, _ in sorted(selected, key=lambda item: item[0])}


def build_context_phrases_streaming(
    input_paths: list[Path],
    min_freq: int,
    min_dominance: float,
    ngram_sizes: tuple[int, ...],
    max_entries: int,
    candidate_limit: int,
    prune_to: int,
    max_rows: int | None = None,
) -> dict[str, str]:
    candidates = mine_candidate_keys(
        input_paths=input_paths,
        ngram_sizes=ngram_sizes,
        candidate_limit=candidate_limit,
        prune_to=prune_to,
        max_rows=max_rows,
    )
    print(f"  retained {len(candidates):,} candidates for exact pass", file=sys.stderr)

    variant_counts = count_candidate_variants(
        input_paths=input_paths,
        ngram_sizes=ngram_sizes,
        candidates=candidates,
        max_rows=max_rows,
    )
    return select_context_phrases(
        variant_counts=variant_counts,
        min_freq=min_freq,
        min_dominance=min_dominance,
        max_entries=max_entries,
    )


def _parse_ngram_sizes(raw_values: list[int]) -> tuple[int, ...]:
    values = tuple(sorted(set(raw_values)))
    if not values or any(value < 2 for value in values):
        raise argparse.ArgumentTypeError("ngram sizes must be integers >= 2")
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build context phrase map with bounded memory usage"
    )
    parser.add_argument(
        "--input",
        nargs="+",
        type=Path,
        default=DEFAULT_INPUTS,
        help="CSV files to process. Defaults to validation corpus only.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/diacritic/context_phrases.json"),
        help="Output JSON path",
    )
    parser.add_argument("--min-freq", type=int, default=50)
    parser.add_argument("--min-dominance", type=float, default=0.85)
    parser.add_argument(
        "--ngram-sizes",
        nargs="+",
        type=int,
        default=[2, 3, 4],
        help="N-gram sizes to extract. Use fewer sizes for faster builds.",
    )
    parser.add_argument("--max-entries", type=int, default=5000)
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=200_000,
        help="Maximum tracked candidate keys before pruning.",
    )
    parser.add_argument(
        "--prune-to",
        type=int,
        default=100_000,
        help="Number of candidate keys to keep after pruning.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional row cap for a quick, lower-quality build.",
    )
    args = parser.parse_args(argv)

    if args.candidate_limit < 1:
        print("Error: --candidate-limit must be positive", file=sys.stderr)
        return 2
    if not (0 < args.prune_to <= args.candidate_limit):
        print("Error: --prune-to must be between 1 and --candidate-limit", file=sys.stderr)
        return 2
    if args.min_freq < 1:
        print("Error: --min-freq must be positive", file=sys.stderr)
        return 2
    if not (0 < args.min_dominance <= 1):
        print("Error: --min-dominance must be in (0, 1]", file=sys.stderr)
        return 2

    try:
        ngram_sizes = _parse_ngram_sizes(args.ngram_sizes)
    except argparse.ArgumentTypeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    missing = [path for path in args.input if not path.exists()]
    if missing:
        print(f"Error: input file not found: {missing[0]}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    print(
        "Building context phrase map with bounded memory "
        f"(inputs={len(args.input)}, ngrams={ngram_sizes}, "
        f"candidate_limit={args.candidate_limit:,})...",
        file=sys.stderr,
    )
    started = time.perf_counter()

    phrases = build_context_phrases_streaming(
        input_paths=list(args.input),
        min_freq=args.min_freq,
        min_dominance=args.min_dominance,
        ngram_sizes=ngram_sizes,
        max_entries=args.max_entries,
        candidate_limit=args.candidate_limit,
        prune_to=args.prune_to,
        max_rows=args.max_rows,
    )

    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(phrases, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    elapsed = time.perf_counter() - started
    print(f"Done: {len(phrases):,} context phrases in {elapsed:.1f}s", file=sys.stderr)
    print(f"Written to {args.output}", file=sys.stderr)

    by_length: Counter[int] = Counter(len(key.split()) for key in phrases)
    for ngram_size in sorted(by_length):
        print(f"  {ngram_size}-grams: {by_length[ngram_size]:,}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
