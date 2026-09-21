# -*- coding: utf-8 -*-
"""[DEBUG-a4f2] Compare OLD (backup) vs NEW diacritic assets objectively.

Evaluates: (1) chat_regression_test.csv pass rate, (2) Test2 rule-based
scorer patterns via the full live pipeline per asset set.
"""
from __future__ import annotations

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.config import get_settings  # noqa: E402
from app.data_manager.pending_service import PendingAbbreviationService  # noqa: E402
from app.bootstrap import build_pipeline  # noqa: E402
from app.normalizer.live_normalizer import LiveNormalizerService  # noqa: E402
from app.normalizer.diacritic_restorer import (  # noqa: E402
    SyncDiacriticRestorer,
    load_word_map,
    load_bigram_freq,
    get_shared_context_phrase_overrides,
)

sys.path.insert(0, os.path.join(HERE, "score_quality.py"))
import score_quality as scorer  # noqa: E402

TAG = "[DEBUG-a4f2]"


def evaluate(asset_dir: str, label: str, test2_text: str) -> None:
    from pathlib import Path

    settings = get_settings()
    wm = load_word_map(Path(asset_dir) / "word_map.json")
    bg = load_bigram_freq(Path(asset_dir) / "bigram_freq.json")
    cp = get_shared_context_phrase_overrides(settings.data_dir)
    restorer = SyncDiacriticRestorer(
        word_map=wm, bigram_freq=bg, context_phrases=cp,
        detection_threshold=settings.diacritic_detection_threshold,
        min_text_length=settings.diacritic_min_text_length,
    )

    # (1) regression suite pass rate
    ok = total = 0
    fails = []
    with open(os.path.join(ROOT, "backend/data/diacritic/chat_regression_test.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            total += 1
            got = restorer.restore(row["no_diacritics"]).restored_text
            exp = row["with_diacritics"]
            fold_got = scorer.fold(got)
            fold_exp = scorer.fold(exp)
            # exact match on the regression ground truth
            if got == exp:
                ok += 1
            else:
                fails.append((row["no_diacritics"], exp, got))
    print(f"{TAG} [{label}] regression exact-match: {ok}/{total}")
    for inp, exp, got in fails[:6]:
        print(f"{TAG}   MISS {inp!r}: expected {exp!r} got {got!r}")

    # (2) Test2 full pipeline + scorer
    PendingAbbreviationService.db_is_ready = lambda self: False
    PendingAbbreviationService.submit_pending_abbreviation = (
        lambda self, abbr, **k: {"abbr": abbr, "status": "IGNORED", "pending_id": None,
                                 "has_suggested": False})
    pipeline = build_pipeline(settings)
    service = LiveNormalizerService(settings, pipeline.pending_service, diacritic_restorer=restorer)
    result = service.normalize_live(test2_text, input_method="paste")
    out_path = os.path.join(HERE, f"Test2.rulebased_{label}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result.primary_output)
    total_hits = 0
    for pattern, _label in scorer.WRONG:
        import re
        total_hits += len(re.findall(pattern, result.primary_output, flags=re.IGNORECASE))
    print(f"{TAG} [{label}] Test2 wrong-pattern hits: {total_hits}")


def main() -> None:
    backup = os.path.join(ROOT, "backend", "data", "diacritic", "backup", "20260921_032912")
    settings = get_settings()
    with open(os.path.join(HERE, "Test2.txt"), encoding="utf-8") as f:
        test2 = f.read()
    evaluate(backup, "OLD", test2)
    evaluate(os.path.join(ROOT, "backend", "data", "diacritic"), "NEW", test2)


if __name__ == "__main__":
    main()
