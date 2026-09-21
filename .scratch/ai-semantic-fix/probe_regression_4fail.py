# -*- coding: utf-8 -*-
"""[DEBUG-r4f1] Probe why 4 regression cases fail with rebuilt assets.

Traces _score_with_bigrams decisions for each failing input, comparing live
assets vs backup assets (20260921_144452). Read-only: loads assets, prints,
writes nothing.
"""
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\admin\Downloads\ChuanHoaTiengViet")
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

import app.normalizer.diacritic_restorer as dr  # noqa: E402

DATA = BACKEND / "data" / "diacritic"
BACKUP = DATA / "backup" / "20260921_144452"

CASES = [
    ("basic_7", "chuc ban ngu ngon nhe", "chúc bạn ngủ ngon nhé"),
    ("basic_8", "may gio roi ban", "mấy giờ rồi bạn"),
    ("short_41", "tot lam", "tốt lắm"),
    ("natural_chat_47", "sao may hom nay ban qua vay", "sao mấy hôm nay bận quá vậy"),
]

ND_KEYS = ["chuc", "ban", "may", "lam", "qua", "tot", "roi", "gio", "hom",
           "nay", "sao", "vay", "ngu", "ngon", "nhe"]
BG_KEYS = ["chúc_bạn", "chức_bạn", "chức_bán", "chúc_bán", "bạn_ngủ", "bán_ngủ",
           "ngủ_ngon", "ngon_nhẹ", "ngon_nhé", "mấy_giờ", "máy_giờ", "rồi_bạn",
           "rồi_bán", "tốt_lắm", "tốt_làm", "bận_quá", "bạn_quá", "bán_quá",
           "quá_vậy", "qua_vậy", "hôm_nay", "máy_hôm", "mấy_hôm", "nay_bận",
           "nay_bạn", "nay_bán", "hôm_bận", "chúc_ngủ"]

_orig_score = dr._score_with_bigrams
TRACE = {"on": False}


def _traced(candidates, prev_candidates, next_candidates, bigram_freq,
            original=None, preserve_original=False):
    result = _orig_score(candidates, prev_candidates, next_candidates,
                         bigram_freq, original=original,
                         preserve_original=preserve_original)
    if TRACE["on"]:
        def sc(c):
            v = 0
            if prev_candidates:
                v += max((bigram_freq.get(f"{p}_{c}", 0) for p in prev_candidates), default=0)
            if next_candidates:
                v += max((bigram_freq.get(f"{c}_{n}", 0) for n in next_candidates), default=0)
            return v
        scores = ", ".join(f"{c}:{sc(c)}" for c in candidates)
        print(f"      [score] {original!r}: ({scores}) => {result!r}")
    return result


dr._score_with_bigrams = _traced


def load_assets(folder: Path):
    wm_path = folder / "word_map.json"
    bg_path = folder / "bigram_freq.json"
    wm = dr.load_word_map(wm_path) if wm_path.exists() else {}
    bg = dr.load_bigram_freq(bg_path) if bg_path.exists() else {}
    return wm, bg


def main() -> None:
    live_wm, live_bg = load_assets(DATA)
    old_wm, old_bg = load_assets(BACKUP)
    ctx = dr.get_shared_context_phrase_overrides(BACKEND / "data")

    print("== inventory ==")
    print(f"  live : word_map={len(live_wm):,} bigram={len(live_bg):,}")
    print(f"  old  : word_map={len(old_wm):,} bigram={len(old_bg):,}")

    print("\n== word_map trap keys (live | old) ==")
    for key in ND_KEYS:
        print(f"  {key:6s} live={live_wm.get(key)}  old={old_wm.get(key)}")

    print("\n== bigram trap keys (live | old) ==")
    for key in BG_KEYS:
        lv, od = live_bg.get(key, 0), old_bg.get(key, 0)
        flag = "  <-- MISSING live" if lv == 0 and od > 0 else ""
        print(f"  {key:12s} live={lv:<8} old={od}{flag}")

    print("\n== context phrase overrides present? ==")
    for nd in [("chuc", "ban"), ("may", "gio"), ("roi", "ban"), ("tot", "lam"),
               ("ban", "qua"), ("hom", "nay")]:
        print(f"  {nd}: {ctx.get(nd)}")

    print("\n== restore trace (live assets) ==")
    for name, text, expected in CASES:
        print(f"\n  [{name}] '{text}' -> expected '{expected}'")
        TRACE["on"] = True
        out, changed, cov, amb = dr._rule_restore(text, live_wm, live_bg, ctx)
        TRACE["on"] = False
        ok = "OK " if out == expected else "FAIL"
        print(f"    => {ok} got: '{out}'  coverage={cov:.2f}")
        if amb:
            print(f"    ambiguous: {amb}")

    print("\n== restore trace (old backup assets, no trace) ==")
    for name, text, expected in CASES:
        out, _, _, amb = dr._rule_restore(text, old_wm, old_bg, ctx)
        ok = "OK " if out == expected else "FAIL"
        print(f"  [{name}] {ok} got: '{out}'  ambiguous={amb}")


if __name__ == "__main__":
    main()
