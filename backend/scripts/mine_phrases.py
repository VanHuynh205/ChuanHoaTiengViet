"""Offline phrase miner over the DataDauCau corpus.

Streams the CSV (header: ``no_diacritics,with_diacritics``) line by line,
counts n-grams 2..max_ngram on the diacritised side, computes PMI as a
quality signal, filters by frequency, and writes ``mined_phrases.json``.

Designed to run on the full 10 M-row train corpus with bounded RAM by
keeping only the n-gram counters in memory and emitting a top-N list at
the end.

Usage::

    python scripts/mine_phrases.py \
        --input data/DataDauCau/sample_5k.csv \
        --output data/phrases/mined_phrases.json \
        --min-freq 3 --max-ngram 5
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator


# Match alphabetic words including Vietnamese diacritics.
_WORD_PATTERN = re.compile(r"[a-zA-ZÀ-ỹ]+", re.UNICODE)


def iter_pairs(csv_path: Path, *, limit: int | None = None) -> Iterator[tuple[str, str]]:
    """Yield ``(no_diacritics, with_diacritics)`` rows, skipping the header."""
    csv.field_size_limit(min(sys.maxsize, 2_147_483_647))
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            return
        if header[:2] != ["no_diacritics", "with_diacritics"]:
            raise ValueError(
                f"Unexpected CSV header in {csv_path}: {header[:2]!r}"
            )
        for index, row in enumerate(reader):
            if limit is not None and index >= limit:
                return
            if len(row) < 2:
                continue
            yield row[0], row[1]


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in _WORD_PATTERN.finditer(text)]


def ngrams(tokens: list[str], n: int) -> Iterable[tuple[str, ...]]:
    if len(tokens) < n:
        return
    for i in range(len(tokens) - n + 1):
        yield tuple(tokens[i : i + n])


def mine(
    csv_path: Path,
    *,
    min_freq: int = 3,
    max_ngram: int = 5,
    limit: int | None = None,
    top_n: int = 50_000,
) -> dict:
    """Return a JSON-ready report. Pure function: no filesystem writes."""
    if max_ngram < 2:
        raise ValueError("max_ngram must be >= 2")

    unigram_counts: Counter[str] = Counter()
    ngram_counts: dict[int, Counter[tuple[str, ...]]] = {
        n: Counter() for n in range(2, max_ngram + 1)
    }
    total_unigrams = 0
    rows_seen = 0

    started = time.perf_counter()
    for _, with_dia in iter_pairs(csv_path, limit=limit):
        tokens = tokenize(with_dia)
        if not tokens:
            continue
        unigram_counts.update(tokens)
        total_unigrams += len(tokens)
        for n in ngram_counts:
            for gram in ngrams(tokens, n):
                ngram_counts[n][gram] += 1
        rows_seen += 1

    phrases: list[dict[str, object]] = []
    for n in range(2, max_ngram + 1):
        for gram, freq in ngram_counts[n].items():
            if freq < min_freq:
                continue
            pmi = _compute_pmi(gram, freq, unigram_counts, total_unigrams)
            phrase = " ".join(gram)
            phrases.append(
                {
                    "phrase": phrase,
                    "expanded": phrase,
                    "freq": freq,
                    "pmi": round(pmi, 6),
                    "ngram": n,
                    "source": "mined",
                    "confidence": _confidence_from_pmi(pmi),
                }
            )

    phrases.sort(key=lambda item: (-int(item["freq"]), -float(item["pmi"]), item["phrase"]))
    if top_n > 0:
        phrases = phrases[:top_n]

    elapsed = time.perf_counter() - started
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_path": str(csv_path),
        "rows_seen": rows_seen,
        "min_freq": min_freq,
        "max_ngram": max_ngram,
        "total_unigrams": total_unigrams,
        "elapsed_seconds": round(elapsed, 3),
        "phrases": phrases,
    }


def _compute_pmi(
    gram: tuple[str, ...],
    freq: int,
    unigram_counts: Counter[str],
    total_unigrams: int,
) -> float:
    if total_unigrams <= 0 or freq <= 0:
        return 0.0
    p_joint = freq / max(total_unigrams, 1)
    p_individual = 1.0
    for token in gram:
        token_count = unigram_counts.get(token, 0)
        if token_count == 0:
            return 0.0
        p_individual *= token_count / total_unigrams
    if p_individual <= 0:
        return 0.0
    return math.log2(p_joint / p_individual)


def _confidence_from_pmi(pmi: float) -> float:
    """Map a PMI value to a confidence in ``[0, 1]`` via a logistic squash."""
    return round(1.0 / (1.0 + math.exp(-0.5 * pmi)), 4)


def write_report(report: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mine phrase n-grams from DataDauCau.")
    parser.add_argument("--input", required=True, type=Path, help="CSV input path")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/phrases/mined_phrases.json"),
        help="JSON output path",
    )
    parser.add_argument("--min-freq", type=int, default=3)
    parser.add_argument("--max-ngram", type=int, default=5)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after N rows (useful for tests).",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=50_000,
        help="Cap the output phrase list (0 = unbounded).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.input.exists():
        print(f"input not found: {args.input}", file=sys.stderr)
        return 2
    report = mine(
        args.input,
        min_freq=args.min_freq,
        max_ngram=args.max_ngram,
        limit=args.limit,
        top_n=args.top_n,
    )
    write_report(report, args.output)
    print(
        f"mined {len(report['phrases'])} phrases from {report['rows_seen']} rows "
        f"in {report['elapsed_seconds']}s -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
