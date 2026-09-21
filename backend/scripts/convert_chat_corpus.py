#!/usr/bin/env python3
"""Convert a raw comment dataset (e.g. UIT-ViSFD) into DataDauCau format.

Input CSVs keep their original columns (index, comment, ...) with an accented
``comment`` column. Output CSVs have exactly two columns:

    no_diacritics,with_diacritics

where ``no_diacritics`` is a synthetic stripped form (NFD marks removed,
đ→d, case preserved) of the accented comment — matching how ViDiacritics
was built.

Usage::

    python scripts/convert_chat_corpus.py \\
        --input data/DataDauCau/chat/_raw/Train.csv ... \\
        --output-dir data/DataDauCau/chat
"""
from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from pathlib import Path


def strip_diacritics(text: str) -> str:
    # Case preserved (mirrors ViDiacritics construction).
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return stripped.replace("đ", "d").replace("Đ", "D")


def clean_comment(text: str) -> str:
    return " ".join((text or "").replace("\r", " ").replace("\n", " ").split())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert raw chat CSVs to DataDauCau format")
    parser.add_argument("--input", nargs="+", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--min-words", type=int, default=3,
                        help="Skip comments with fewer alphabetic words")
    args = parser.parse_args(argv)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    total_in = total_out = 0
    for src in args.input:
        if not src.exists():
            print(f"ERROR: missing {src}", file=sys.stderr)
            return 2
        seen: set[str] = set()
        rows_out = 0
        dst = args.output_dir / f"{src.stem}.csv"
        with src.open(encoding="utf-8-sig", newline="") as fin, \
                dst.open("w", encoding="utf-8", newline="") as fout:
            reader = csv.DictReader(fin)
            writer = csv.writer(fout)
            writer.writerow(["no_diacritics", "with_diacritics"])
            for row in reader:
                total_in += 1
                with_d = clean_comment(row.get("comment") or "")
                if not with_d:
                    continue
                key = " ".join(with_d.casefold().split())
                if key in seen:
                    continue
                if len(with_d.split()) < args.min_words:
                    continue
                seen.add(key)
                writer.writerow([strip_diacritics(with_d), with_d])
                rows_out += 1
        total_out += rows_out
        print(f"{src.name}: {rows_out:,} rows written -> {dst} "
              f"(input rows: {total_in - total_out + rows_out:,})", file=sys.stderr)
    print(f"TOTAL: {total_out:,} rows", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
