#!/usr/bin/env python3
"""Export dbo.normalization_history into DataDauCau chat-corpus format.

The user's pasted text is chat-domain truth: when the input already carries
diacritics it becomes ``with_diacritics`` directly and ``no_diacritics`` is
produced by mechanically stripping accents (NFD + đ→d). This avoids training
the assets on the system's own output errors.

Long documents (~1000 words) are the most valuable rows — they are cut into
sliding windows of ``--window-words`` tokens instead of being dropped by a
max-words filter (the old behavior silently discarded them, leaving only a
handful of short rows).

Modes::

    --source input   (default) with_diacritics = user input (must be accented)
    --source output  legacy: with_diacritics = system normalized output

Deduplicates by output text and skips degenerate rows. Run it from backend/
in a normal terminal (SQL Server needs your Windows credentials)::

    python scripts/export_history_corpus.py \\
        --output data/DataDauCau/chat/history_export.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.data_manager.db import create_sqlalchemy_engine  # noqa: E402
from app.utils.diacritic_detect import _count_vowels  # noqa: E402


def clean(value: str | None) -> str:
    return " ".join((value or "").replace("\r", " ").replace("\n", " ").split())


def strip_diacritics(text: str) -> str:
    """Remove Vietnamese tone marks; "đ" does not decompose under NFD."""
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.replace("đ", "d").replace("Đ", "D")


def is_mostly_accented(text: str, min_ratio: float) -> bool:
    if min_ratio <= 0:
        return True
    with_d, total = _count_vowels(text)
    return total > 0 and with_d / total >= min_ratio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export normalization history as corpus")
    parser.add_argument("--output", type=Path,
                        default=Path("data/DataDauCau/chat/history_export.csv"))
    parser.add_argument("--source", choices=("input", "output"), default="input",
                        help="Which column is the accented ground truth "
                             "(default: input — the user's own text).")
    parser.add_argument("--accented-min-ratio", type=float, default=0.5,
                        help="Min accented-vowel ratio for the truth column "
                             "(0 disables the filter).")
    parser.add_argument("--window-words", type=int, default=120,
                        help="Cut long documents into windows of this many "
                             "words (0 = keep whole rows).")
    parser.add_argument("--min-words", type=int, default=4)
    parser.add_argument("--limit", type=int, default=200_000)
    args = parser.parse_args(argv)

    engine = create_sqlalchemy_engine(get_settings())
    if engine is None:
        print("ERROR: sqlalchemy/pyodbc chưa sẵn sàng (kiểm tra .venv đã cài đủ deps)",
              file=sys.stderr)
        return 3
    query = text(
        "SELECT input_text, output_text FROM dbo.normalization_history "
        "WHERE output_text IS NOT NULL AND output_text <> '' "
        "ORDER BY created_at DESC OFFSET 0 ROWS FETCH NEXT :limit ROWS ONLY"
    )
    seen: set[str] = set()
    written = scanned = skipped_ratio = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with engine.connect() as conn, \
            args.output.open("w", encoding="utf-8", newline="") as fout:
        writer = csv.writer(fout)
        writer.writerow(["no_diacritics", "with_diacritics"])
        for input_text, output_text in conn.execute(query, {"limit": args.limit}):
            scanned += 1
            if args.source == "input":
                # User text is the truth; the no-diacritic side is derived so
                # the pair stays perfectly token-aligned.
                truth = clean(input_text)
                no_d_full = strip_diacritics(truth)
            else:
                # Legacy mode: trust the system output, raw input as no-d side.
                truth = clean(output_text)
                no_d_full = clean(input_text)
            if not truth or not no_d_full:
                continue
            if not is_mostly_accented(truth, args.accented_min_ratio):
                skipped_ratio += 1
                continue
            truth_words = truth.split()
            other_words = no_d_full.split()
            if len(truth_words) != len(other_words):
                continue  # builder drops misaligned rows anyway
            size = args.window_words if args.window_words > 0 else len(truth_words)
            for start in range(0, len(truth_words), size):
                t_chunk = truth_words[start : start + size]
                o_chunk = other_words[start : start + size]
                if len(t_chunk) < args.min_words:
                    continue
                with_d = " ".join(t_chunk)
                no_d = " ".join(o_chunk)
                key = with_d.casefold()
                if key in seen:
                    continue
                seen.add(key)
                writer.writerow([no_d, with_d])
                written += 1
    print(f"scanned {scanned:,} rows, wrote {written:,} corpus rows "
          f"({skipped_ratio:,} skipped: not accented enough) -> {args.output}",
          file=sys.stderr)
    if written == 0:
        print("NOTE: 0 rows — bảng trống hay SQL chưa kết nối? Xem thông báo lỗi ở trên.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
