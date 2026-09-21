"""Benchmark diacritic restoration against a DataDauCau CSV file.

Usage::

    python scripts/eval_diacritic.py \\
        --input data/DataDauCau/ViDiacritics_test.csv \\
        --word-map data/diacritic/word_map.json \\
        --bigram-freq data/diacritic/bigram_freq.json \\
        --sample 500 \\
        --engine rule \\
        --output data/diacritic/eval_results.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from scripts.diacritic_corpus import iter_diacritic_pairs
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from diacritic_corpus import iter_diacritic_pairs


def _token_accuracy(reference: str, hypothesis: str) -> float:
    ref_tokens = reference.strip().split()
    hyp_tokens = hypothesis.strip().split()
    if not ref_tokens:
        return 1.0
    matches = sum(1 for r, h in zip(ref_tokens, hyp_tokens) if r == h)
    return matches / len(ref_tokens)


def _sentence_exact(reference: str, hypothesis: str) -> bool:
    return reference.strip() == hypothesis.strip()


def load_samples(input_path: Path, sample_size: int, seed: int = 42) -> list[tuple[str, str]]:
    pairs = list(iter_diacritic_pairs([input_path]))

    if sample_size >= len(pairs):
        return pairs

    # Deterministic benchmark sampling; this is not security-sensitive randomness.
    rng = random.Random(seed)  # nosec B311
    return rng.sample(pairs, sample_size)


def evaluate_rule_only(
    samples: list[tuple[str, str]],
    word_map: dict[str, list[str]],
    bigram_freq: dict[str, int] | None = None,
) -> dict:
    from app.normalizer.diacritic_restorer import _rule_restore

    token_accs: list[float] = []
    exact_matches = 0
    latencies: list[float] = []

    for no_d, with_d in samples:
        started = time.perf_counter()
        restored, _, _, _ = _rule_restore(no_d, word_map, bigram_freq)
        elapsed_ms = (time.perf_counter() - started) * 1000

        token_accs.append(_token_accuracy(with_d, restored))
        if _sentence_exact(with_d, restored):
            exact_matches += 1
        latencies.append(elapsed_ms)

    latencies.sort()
    p95_index = min(int(len(latencies) * 0.95), len(latencies) - 1) if latencies else 0
    return {
        "engine": "rule",
        "sample_size": len(samples),
        "token_accuracy": round(sum(token_accs) / len(token_accs), 4) if token_accs else 0,
        "sentence_exact": round(exact_matches / len(samples), 4) if samples else 0,
        "latency_p50_ms": round(latencies[len(latencies) // 2], 1) if latencies else 0,
        "latency_p95_ms": round(latencies[p95_index], 1) if latencies else 0,
    }


def evaluate_baseline(samples: list[tuple[str, str]]) -> dict:
    token_accs: list[float] = []
    exact_matches = 0

    for no_d, with_d in samples:
        token_accs.append(_token_accuracy(with_d, no_d))
        if _sentence_exact(with_d, no_d):
            exact_matches += 1

    return {
        "engine": "baseline",
        "sample_size": len(samples),
        "token_accuracy": round(sum(token_accs) / len(token_accs), 4) if token_accs else 0,
        "sentence_exact": round(exact_matches / len(samples), 4) if samples else 0,
        "latency_p50_ms": 0,
        "latency_p95_ms": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate diacritic restoration")
    parser.add_argument("--input", required=True, type=Path, help="Path to CSV")
    parser.add_argument("--word-map", required=True, type=Path, help="Path to word_map.json")
    parser.add_argument(
        "--bigram-freq",
        type=Path,
        default=None,
        help="Optional path to bigram_freq.json",
    )
    parser.add_argument("--sample", type=int, default=500)
    parser.add_argument("--engine", default="rule", choices=["rule", "baseline"])
    parser.add_argument("--output", required=True, type=Path, help="Output JSON path")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    word_map: dict[str, list[str]] = {}
    if args.word_map.exists():
        with args.word_map.open(encoding="utf-8") as handle:
            raw_word_map = json.load(handle)
        word_map = {k: (v if isinstance(v, list) else [v]) for k, v in raw_word_map.items()}

    bigram_freq: dict[str, int] = {}
    if args.bigram_freq and args.bigram_freq.exists():
        with args.bigram_freq.open(encoding="utf-8") as handle:
            bigram_freq = json.load(handle)

    samples = load_samples(args.input, args.sample)
    print(f"Evaluating {len(samples)} samples with engine={args.engine}...", file=sys.stderr)

    if args.engine == "baseline":
        result = evaluate_baseline(samples)
    else:
        result = evaluate_rule_only(samples, word_map, bigram_freq)

    from datetime import datetime, timezone

    result["ran_at"] = datetime.now(timezone.utc).isoformat()
    result["input"] = str(args.input)
    result["word_map"] = str(args.word_map)
    result["bigram_freq"] = str(args.bigram_freq) if args.bigram_freq else None

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)

    print(json.dumps(result, indent=2), file=sys.stderr)
    print(f"Written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
