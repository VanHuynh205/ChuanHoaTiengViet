# -*- coding: utf-8 -*-
"""[DEBUG-r4f1] Run the 52-case regression CSV against an arbitrary asset dir.

Usage (from backend/):
    ..\\.venv\\Scripts\\python.exe -X utf8 ..\\.scratch\\ai-semantic-fix\\run_regression_against.py <asset_dir>

Replicates tests/test_diacritic_regression.py logic (builtin context phrases,
threshold 0.6 per case) without touching the live data/diacritic assets.
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(r"C:\Users\admin\Downloads\ChuanHoaTiengViet")
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from app.normalizer.diacritic_restorer import (  # noqa: E402
    _rule_restore,
    load_bigram_freq,
    load_word_map,
)

TEST_CSV = BACKEND / "data" / "diacritic" / "chat_regression_test.csv"


def main() -> int:
    asset_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else BACKEND / "data" / "diacritic"
    wm = load_word_map(asset_dir / "word_map.json")
    bg = load_bigram_freq(asset_dir / "bigram_freq.json")

    with TEST_CSV.open(encoding="utf-8") as f:
        cases = list(csv.DictReader(f))

    stats: dict[str, list[float]] = defaultdict(list)
    fails: list[str] = []
    for idx, row in enumerate(cases):
        inp, exp = row["no_diacritics"], row["with_diacritics"]
        cat = row.get("category", "unknown")
        got, _, _, _ = _rule_restore(inp, wm, bg)
        ref, hyp = exp.split(), got.split()
        acc = sum(1 for r, h in zip(ref, hyp) if r == h) / len(ref) if ref else 1.0
        stats[cat].append(acc)
        if cat != "ambiguous" and acc < 0.6:
            fails.append(f"  [{cat}_{idx}] acc={acc:.0%} in={inp!a} got={got!a} exp={exp!a}")

    all_accs = [a for accs in stats.values() for a in accs]
    for cat in sorted(stats):
        accs = stats[cat]
        print(f"  {cat:<15s} avg={sum(accs)/len(accs):6.1%}  perfect={sum(1 for a in accs if a>=1)}/{len(accs)}")
    overall = sum(all_accs) / len(all_accs)
    print(f"  {'OVERALL':<15s} avg={overall:6.1%}  perfect={sum(1 for a in all_accs if a>=1)}/{len(all_accs)}")
    # Gate matches pytest: threshold 0.6 per case, but "ambiguous" cases are
    # exempt (threshold 0.0) — they are known-hard, AI review handles them.
    print(f"  GATE: {'FAIL' if fails else 'PASS'}  ({len(fails)} non-ambiguous case under 60%)")
    for line in fails[:10]:
        print(line)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
