#!/usr/bin/env python3
"""Memory-safe streaming builder for diacritic assets (word_map + bigram_freq).

Designed for machines with limited RAM (16GB).
Key features:
  - Single-pass: builds word_map AND bigram in one read
  - Chunked processing with periodic bigram pruning to cap memory
  - Checkpoint after each chunk -- resume on crash
  - Progressive: run val.csv first, then merge train.csv chunks later

Usage examples:

  # Phase 1: val.csv only (~2 min, safe on any machine)
  python scripts/build_diacritic_streaming.py --input data/DataDauCau/ViDiacritics_val.csv

  # Phase 2: add train.csv (chunked + checkpoint, ~15 min)
  python scripts/build_diacritic_streaming.py --input data/DataDauCau/ViDiacritics_train.csv --merge

  # Full run with custom chunk size
  python scripts/build_diacritic_streaming.py \\
      --input data/DataDauCau/ViDiacritics_val.csv data/DataDauCau/ViDiacritics_train.csv \\
      --chunk-size 300000

  # Resume from last checkpoint after crash
  python scripts/build_diacritic_streaming.py \\
      --input data/DataDauCau/ViDiacritics_train.csv --resume
"""

from __future__ import annotations

import argparse
import csv
import json
import string
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
STRIP_CHARS = string.punctuation + "\u2026\u201c\u201d\u2018\u2019"
NO_DIACRITICS_COL = "no_diacritics"
WITH_DIACRITICS_COL = "with_diacritics"

DEFAULT_OUTPUT_DIR = Path("data/diacritic")
CHECKPOINT_DIR = Path("data/diacritic/.checkpoints")

DEFAULT_CHUNK_SIZE = 500_000
DEFAULT_MIN_FREQ = 2
# The known-good original asset set kept up to 8 diacritic forms per
# no-diacritic key ("lam" needs "lắm" at rank 6, "ban" needs "bận" at rank 8).
# Cutting at 5 silently drops exactly the chat-critical low-rank forms.
DEFAULT_MAX_ENTRIES = 8
DEFAULT_BIGRAM_TOP_N = 100_000
# Pruning at every chunk boundary is LOSSY in a way that permanently resets
# counts: a bigram evicted while still accumulating (e.g. "chúc_bạn" sitting
# at count 45 when the keep-threshold passes 50) restarts from zero and can
# never recover, so real mid-frequency collocations vanish from the final
# asset even when they beat the top-N cut. The keep limit must stay WELL
# above the final top-N cutoff band (220k, cutoff ≈80): with 1.5M slots the
# prune threshold stays in the junk tail (count ~3-6) and no real bigram is
# ever reset. Peak memory ~2.6M entries ≈ 1GB — safe on 16GB.
DEFAULT_BIGRAM_PRUNE_KEEP = 1_500_000


# ---------------------------------------------------------------------------
# Token helpers (inlined to avoid import issues when running standalone)
# ---------------------------------------------------------------------------
def clean_token(token: str) -> str:
    cleaned = token.lower().strip(STRIP_CHARS)
    return cleaned if cleaned.isalpha() else ""


def tokenize_words(text: str) -> list[str]:
    return [c for t in text.split() if (c := clean_token(t))]


# ---------------------------------------------------------------------------
# Checkpoint I/O
# ---------------------------------------------------------------------------
def _checkpoint_path(tag: str) -> Path:
    return CHECKPOINT_DIR / f"ckpt_{tag}.json"


def save_checkpoint(
    tag: str,
    word_counts: dict[str, Counter],
    bigram_counts: Counter,
    files_done: list[str],
    lines_done: int,
    current_file: str,
    current_offset: int,
    prune_keep: int = DEFAULT_BIGRAM_PRUNE_KEEP,
) -> None:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "files_done": files_done,
        "lines_done": lines_done,
        "current_file": current_file,
        "current_offset": current_offset,
        "word_counts": {
            k: dict(v) for k, v in word_counts.items()
        },
        "bigram_counts": dict(bigram_counts.most_common(prune_keep)),
    }
    tmp = _checkpoint_path(tag).with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    tmp.replace(_checkpoint_path(tag))
    _print(f"  [checkpoint] saved at line {lines_done:,}, "
           f"word_map={len(word_counts):,}, bigrams={len(bigram_counts):,}")


def load_checkpoint(tag: str) -> dict | None:
    path = _checkpoint_path(tag)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    _print(f"  [checkpoint] resumed from line {data['lines_done']:,}")
    return data


def clear_checkpoints(tag: str) -> None:
    path = _checkpoint_path(tag)
    if path.exists():
        path.unlink()


# ---------------------------------------------------------------------------
# Core streaming builder
# ---------------------------------------------------------------------------
def build_streaming(
    input_paths: list[Path],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    min_freq: int = DEFAULT_MIN_FREQ,
    max_entries_per_word: int = DEFAULT_MAX_ENTRIES,
    bigram_top_n: int = DEFAULT_BIGRAM_TOP_N,
    bigram_prune_keep: int = DEFAULT_BIGRAM_PRUNE_KEEP,
    resume: bool = False,
    checkpoint_tag: str = "streaming",
    weights: dict[str, float] | None = None,
) -> tuple[dict[str, list[str]], dict[str, int]]:
    """Build word_map and bigram_freq in a single memory-bounded pass."""

    weights = weights or {}
    word_counts: dict[str, Counter] = defaultdict(Counter)
    bigram_counts: Counter = Counter()
    files_done: list[str] = []
    total_lines = 0
    resume_file = ""
    resume_offset = 0

    # Try to resume from checkpoint
    if resume:
        ckpt = load_checkpoint(checkpoint_tag)
        if ckpt:
            for k, v in ckpt["word_counts"].items():
                word_counts[k] = Counter(v)
            bigram_counts = Counter(ckpt["bigram_counts"])
            files_done = ckpt["files_done"]
            total_lines = ckpt["lines_done"]
            resume_file = ckpt.get("current_file", "")
            resume_offset = ckpt.get("current_offset", 0)
        else:
            _print("  No checkpoint found, starting fresh.")

    started = time.perf_counter()
    chunk_lines = 0
    prune_count = 0

    for file_path in input_paths:
        file_str = str(file_path)

        # Skip files already fully processed
        if file_str in files_done:
            _print(f"  Skipping {file_path.name} (already done)")
            continue

        _print(f"  Processing {file_path.name} ({_file_size_mb(file_path):.0f}MB)...")

        skip_to = resume_offset if file_str == resume_file else 0
        line_in_file = 0

        with file_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            _validate_columns(file_path, reader.fieldnames)

            for row in reader:
                line_in_file += 1

                # Skip lines before resume point
                if line_in_file <= skip_to:
                    continue

                no_d = (row.get(NO_DIACRITICS_COL) or "").strip()
                with_d = (row.get(WITH_DIACRITICS_COL) or "").strip()
                if not no_d or not with_d:
                    continue

                # Domain weighting: a chat-domain CSV can be counted with a
                # multiplier so its statistics are not drowned by a much
                # larger news corpus. Counts become floats; JSON handles it.
                weight = float(weights.get(str(file_path.resolve()), 1.0))

                # --- Word map accumulation ---
                nd_tokens = no_d.split()
                wd_tokens = with_d.split()
                if len(nd_tokens) == len(wd_tokens):
                    for nd_tok, wd_tok in zip(nd_tokens, wd_tokens):
                        nd_c = clean_token(nd_tok)
                        wd_c = clean_token(wd_tok)
                        if nd_c and wd_c:
                            word_counts[nd_c][wd_c] += weight

                # --- Bigram accumulation ---
                words = tokenize_words(with_d)
                for i in range(len(words) - 1):
                    bigram_counts[f"{words[i]}_{words[i+1]}"] += weight

                total_lines += 1
                chunk_lines += 1

                # Progress
                if total_lines % 200_000 == 0:
                    elapsed = time.perf_counter() - started
                    rate = total_lines / elapsed if elapsed > 0 else 0
                    _print(f"  {total_lines:>10,} lines | "
                           f"{rate:,.0f} lines/s | "
                           f"words={len(word_counts):,} | "
                           f"bigrams={len(bigram_counts):,}")

                # Chunk boundary: prune bigrams + checkpoint
                if chunk_lines >= chunk_size:
                    # Prune bigrams to cap memory
                    if len(bigram_counts) > bigram_prune_keep * 1.5:
                        before = len(bigram_counts)
                        bigram_counts = Counter(
                            dict(bigram_counts.most_common(bigram_prune_keep))
                        )
                        prune_count += 1
                        _print(f"  [prune #{prune_count}] bigrams {before:,} -> "
                               f"{len(bigram_counts):,}")

                    # Save checkpoint
                    save_checkpoint(
                        checkpoint_tag,
                        word_counts,
                        bigram_counts,
                        files_done,
                        total_lines,
                        file_str,
                        line_in_file,
                        prune_keep=bigram_prune_keep,
                    )
                    chunk_lines = 0

        files_done.append(file_str)
        _print(f"  Finished {file_path.name} ({line_in_file:,} lines)")

        # Checkpoint after finishing each file
        save_checkpoint(
            checkpoint_tag,
            word_counts,
            bigram_counts,
            files_done,
            total_lines,
            "",
            0,
            prune_keep=bigram_prune_keep,
        )

    elapsed = time.perf_counter() - started
    _print(f"\n  Total: {total_lines:,} lines in {elapsed:.1f}s")
    _print(f"  Unique no-diacritic words: {len(word_counts):,}")
    _print(f"  Unique bigrams (pre-filter): {len(bigram_counts):,}")

    # --- Build final word_map ---
    word_map: dict[str, list[str]] = {}
    for nd_word, counter in sorted(word_counts.items()):
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

    # --- Build final bigram_freq ---
    bigram_freq = {
        key: count
        for key, count in bigram_counts.most_common(bigram_top_n)
        if count >= min_freq
    }

    _print(f"  Final word_map: {len(word_map):,} entries")
    _print(f"  Final bigram_freq: {len(bigram_freq):,} entries")

    return word_map, bigram_freq


# ---------------------------------------------------------------------------
# Merge helper
# ---------------------------------------------------------------------------
def merge_into_existing(
    new_word_map: dict[str, list[str]],
    new_bigram: dict[str, int],
    output_dir: Path,
    max_entries_per_word: int = DEFAULT_MAX_ENTRIES,
    bigram_top_n: int = DEFAULT_BIGRAM_TOP_N,
) -> tuple[dict[str, list[str]], dict[str, int]]:
    """Merge new results into existing word_map.json and bigram_freq.json."""
    wm_path = output_dir / "word_map.json"
    bg_path = output_dir / "bigram_freq.json"

    existing_wm: dict[str, list[str]] = {}
    existing_bg: dict[str, int] = {}

    if wm_path.exists():
        with wm_path.open(encoding="utf-8") as f:
            existing_wm = json.load(f)
        _print(f"  Merging into existing word_map ({len(existing_wm):,} entries)")

    if bg_path.exists():
        with bg_path.open(encoding="utf-8") as f:
            existing_bg = json.load(f)
        _print(f"  Merging into existing bigram_freq ({len(existing_bg):,} entries)")

    # Merge word_map: preserve existing rankings, only add genuinely new entries
    merged_wm = {**new_word_map, **existing_wm}

    # Merge bigram: keep existing frequencies (more precise), only add new keys
    merged_bg = dict(existing_bg)
    for key, count in new_bigram.items():
        if key not in merged_bg:
            merged_bg[key] = count
    # Trim to top_n by frequency
    if len(merged_bg) > bigram_top_n:
        merged_bg = dict(
            sorted(merged_bg.items(), key=lambda x: -x[1])[:bigram_top_n]
        )

    _print(f"  Merged word_map: {len(merged_wm):,} entries "
           f"(was {len(existing_wm):,}, new added {len(merged_wm) - len(existing_wm):,})")
    _print(f"  Merged bigram_freq: {len(merged_bg):,} entries")

    return merged_wm, merged_bg


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def write_assets(
    word_map: dict[str, list[str]],
    bigram_freq: dict[str, int],
    output_dir: Path,
    input_paths: list[Path],
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    wm_path = output_dir / "word_map.json"
    bg_path = output_dir / "bigram_freq.json"

    _write_json(wm_path, word_map)
    _write_json(bg_path, bigram_freq)

    from datetime import datetime, timezone
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": [str(p) for p in input_paths],
        "word_map_entries": len(word_map),
        "bigram_entries": len(bigram_freq),
        "builder": "build_diacritic_streaming.py",
    }
    _write_json(output_dir / "diacritic_assets_manifest.json", manifest)

    _print(f"\n  Written word_map.json ({len(word_map):,} entries)")
    _print(f"  Written bigram_freq.json ({len(bigram_freq):,} entries)")
    return manifest


def _write_json(path: Path, payload: object) -> None:
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2,
                  sort_keys=isinstance(payload, dict))
        f.write("\n")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def _print(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _file_size_mb(path: Path) -> float:
    try:
        return path.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0


def _validate_columns(path: Path, fieldnames: list[str] | None) -> None:
    fields = set(fieldnames or [])
    required = {NO_DIACRITICS_COL, WITH_DIACRITICS_COL}
    if not required.issubset(fields):
        raise ValueError(
            f"{path} must have columns: {sorted(required)}; got: {fieldnames}"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Memory-safe streaming builder for diacritic assets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Phase 1: val.csv only (fast, safe)
  python scripts/build_diacritic_streaming.py --input data/DataDauCau/ViDiacritics_val.csv

  # Phase 2: merge train.csv
  python scripts/build_diacritic_streaming.py --input data/DataDauCau/ViDiacritics_train.csv --merge

  # Resume after crash
  python scripts/build_diacritic_streaming.py --input data/DataDauCau/ViDiacritics_train.csv --resume

  # Quick test with sample
  python scripts/build_diacritic_streaming.py --input data/DataDauCau/sample_5k.csv
        """,
    )
    parser.add_argument(
        "--input", nargs="+", type=Path,
        help="CSV files to process",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE,
        help=f"Lines per chunk (default: {DEFAULT_CHUNK_SIZE:,})",
    )
    parser.add_argument(
        "--min-freq", type=int, default=DEFAULT_MIN_FREQ,
        help=f"Min frequency to include (default: {DEFAULT_MIN_FREQ})",
    )
    parser.add_argument(
        "--max-entries-per-word", type=int, default=DEFAULT_MAX_ENTRIES,
        help=f"Max diacritic forms per word (default: {DEFAULT_MAX_ENTRIES})",
    )
    parser.add_argument(
        "--bigram-top-n", type=int, default=DEFAULT_BIGRAM_TOP_N,
        help=f"Max bigrams to keep (default: {DEFAULT_BIGRAM_TOP_N:,})",
    )
    parser.add_argument(
        "--bigram-prune-keep", type=int, default=DEFAULT_BIGRAM_PRUNE_KEEP,
        help=f"Bigrams to keep during pruning (default: {DEFAULT_BIGRAM_PRUNE_KEEP:,})",
    )
    parser.add_argument(
        "--merge", action="store_true",
        help="Merge results into existing word_map.json/bigram_freq.json",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from last checkpoint",
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Delete checkpoints and start fresh",
    )
    parser.add_argument(
        "--weight", action="append", default=[], metavar="PATH=FLOAT",
        help="Count a file's rows with a multiplier (repeatable), e.g. "
             "--weight data/DataDauCau/chat.csv=3 to boost chat-domain "
             "statistics against a larger news corpus.",
    )
    args = parser.parse_args(argv)

    if args.clean:
        clear_checkpoints("streaming")
        _print("Checkpoints cleared.")
        if not args.input:
            return 0

    if not args.input:
        parser.print_help()
        return 1

    missing = [p for p in args.input if not p.exists()]
    if missing:
        _print(f"Error: file not found: {missing[0]}")
        return 2

    weights: dict[str, float] = {}
    for item in args.weight:
        if "=" not in item:
            _print(f"Error: --weight expects PATH=FLOAT, got: {item}")
            return 2
        path_str, _, raw = item.rpartition("=")
        try:
            weights[str(Path(path_str).resolve())] = float(raw)
        except ValueError:
            _print(f"Error: --weight multiplier must be a number, got: {item}")
            return 2

    _print("=" * 60)
    _print("Diacritic Assets Builder (streaming)")
    _print("=" * 60)
    total_size = sum(_file_size_mb(p) for p in args.input)
    _print(f"  Files: {len(args.input)}, total {total_size:.0f}MB")
    _print(f"  Chunk size: {args.chunk_size:,} lines")
    _print(f"  Bigram prune keep: {args.bigram_prune_keep:,}")
    _print(f"  Mode: {'merge' if args.merge else 'overwrite'}")
    _print("")

    word_map, bigram_freq = build_streaming(
        input_paths=args.input,
        chunk_size=args.chunk_size,
        min_freq=args.min_freq,
        max_entries_per_word=args.max_entries_per_word,
        bigram_top_n=args.bigram_top_n,
        bigram_prune_keep=args.bigram_prune_keep,
        resume=args.resume,
        weights=weights,
    )

    if args.merge:
        word_map, bigram_freq = merge_into_existing(
            word_map, bigram_freq, args.output_dir,
            max_entries_per_word=args.max_entries_per_word,
            bigram_top_n=args.bigram_top_n,
        )

    write_assets(word_map, bigram_freq, args.output_dir, args.input)

    # Clean up checkpoints on success
    clear_checkpoints("streaming")
    _print("\n  Checkpoints cleaned up. Done!")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
