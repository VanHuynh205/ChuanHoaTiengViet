# -*- coding: utf-8 -*-
"""[DEBUG-r4f1] Acceptance checks for rebuilt diacritic assets.

Verifies the asset layer no longer discards the evidence the regression
cases need (see .scratch/ai-semantic-fix/diag_asset_diff.md):
  - word_map keeps low-rank chat forms (lắm rank-6 of lam, bận rank-8 of ban)
  - bigram_freq keeps mid-frequency news collocations (chúc_bạn ≥90, mấy_giờ ≥81)
  - the final top-N cut did not rise above the old build's (≤80-ish)

Usage (from backend/):
    ..\\.venv\\Scripts\\python.exe -X utf8 ..\\.scratch\\ai-semantic-fix\\accept_assets.py [asset_dir]
"""
import json
import sys
from pathlib import Path

BACKEND = Path(r"C:\Users\admin\Downloads\ChuanHoaTiengViet\backend")


def main() -> int:
    asset_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else BACKEND / "data" / "diacritic"
    wm = json.loads((asset_dir / "word_map.json").read_text(encoding="utf-8"))
    bg = json.loads((asset_dir / "bigram_freq.json").read_text(encoding="utf-8"))

    counts = sorted(bg.values(), reverse=True)
    checks: list[tuple[str, bool, object]] = [
        ("word_map['lam'] contains 'lắm'", "lắm" in wm.get("lam", []), wm.get("lam")),
        ("word_map['ban'] contains 'bận'", "bận" in wm.get("ban", []), wm.get("ban")),
        ("word_map['may'] contains 'mấy'", "mấy" in wm.get("may", []), wm.get("may")),
        ("word_map['chuc'] contains 'chúc'", "chúc" in wm.get("chuc", []), wm.get("chuc")),
        ("bigram chúc_bạn >= 90", bg.get("chúc_bạn", 0) >= 90, bg.get("chúc_bạn", 0)),
        ("bigram mấy_giờ >= 81", bg.get("mấy_giờ", 0) >= 81, bg.get("mấy_giờ", 0)),
        ("bigram rồi_bạn >= 102", bg.get("rồi_bạn", 0) >= 102, bg.get("rồi_bạn", 0)),
        ("bigram tốt_lắm >= 267", bg.get("tốt_lắm", 0) >= 267, bg.get("tốt_lắm", 0)),
        ("bigram bạn_ngủ >= 209", bg.get("bạn_ngủ", 0) >= 209, bg.get("bạn_ngủ", 0)),
        ("bigramngủ_ngon >= 1260", bg.get("ngủ_ngon", 0) >= 1260, bg.get("ngủ_ngon", 0)),
        ("bigram entries >= 200000", len(bg) >= 200_000, len(bg)),
        ("final cutoff <= 80", counts[-1] <= 80, counts[-1]),
    ]
    failed = 0
    for name, ok, detail in checks:
        if not ok:
            failed += 1
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  (got: {detail})")
    print(f"  {'ACCEPTED' if failed == 0 else 'REJECTED'}: {asset_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
