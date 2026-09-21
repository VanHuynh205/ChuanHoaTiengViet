# -*- coding: utf-8 -*-
"""[DEBUG-dl7] diagnose_layers.py — Layer-by-layer diagnosis of the Vietnamese
normalizer on broken chat text.

Layers probed:
  L0 spelling     apply_known_spelling (normalize_live pre-step)
  L1 restorer     SyncDiacriticRestorer (word_map + bigram + context-phrase fold)
  L2 phrase       PhraseNormalizer + PhraseIndex (live_data overrides/db/mined)
  L3 abbr         elongation + approved_details + expand_abbreviation
  FULL            LiveNormalizerService.normalize_live(input_method="paste")

Run:
  C:\\Users\\admin\\Downloads\\ChuanHoaTiengViet\\.venv\\Scripts\\python.exe \\
      .scratch/ai-semantic-fix/diagnose_layers.py
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

try:  # keep Vietnamese output intact when captured by pwsh
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TAG = "[DEBUG-dl7]"


def patch_db_free() -> None:
    """[DEBUG-dl7] DB-free: JSON bootstrap only, pending writes are no-ops."""
    from app.data_manager.pending_service import PendingAbbreviationService

    def _no_db(self):  # noqa: ANN001
        return False

    def _no_submit(self, abbr, **_kwargs):  # noqa: ANN001
        return {"abbr": abbr, "status": "IGNORED", "pending_id": None,
                "has_suggested": False}

    PendingAbbreviationService.db_is_ready = _no_db
    PendingAbbreviationService.submit_pending_abbreviation = _no_submit


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def has_word(text: str, phrase: str) -> bool:
    """Word-boundary, exact (diacritics-sensitive) search on NFC text."""
    if not phrase:
        return False
    return re.search(r"(?<!\w)" + re.escape(nfc(phrase)) + r"(?!\w)", nfc(text)) is not None


def fold(text: str) -> str:
    from app.normalizer.live_normalizer import _fold_text_for_span_match
    return _fold_text_for_span_match(text)


def main() -> None:
    patch_db_free()
    from app.config import get_settings
    from app.bootstrap import build_pipeline
    from app.normalizer.live_normalizer import LiveNormalizerService
    from app.normalizer.abbreviation import expand_abbreviation
    from app.normalizer.diacritic_restorer import (
        SyncDiacriticRestorer,
        get_shared_bigram_freq,
        get_shared_context_phrase_overrides,
        get_shared_word_map,
        _context_phrase_overrides,
    )
    from app.normalizer.elongation import normalize_elongated_word
    from app.normalizer.spelling import apply_known_spelling
    from app.utils.text_utils import capture_token_layout, join_scan_tokens, tokenize_for_scan

    settings = get_settings()
    print(f"{TAG} data_dir={settings.data_dir}")
    print(f"{TAG} db_is_ready after patch -> ", end="")
    from app.data_manager.pending_service import PendingAbbreviationService
    print(PendingAbbreviationService(settings).db_is_ready())

    pipeline = build_pipeline(settings)
    word_map = get_shared_word_map(settings.data_dir)
    bigram_freq = get_shared_bigram_freq(settings.data_dir)
    context_phrases = get_shared_context_phrase_overrides(settings.data_dir)
    restorer = SyncDiacriticRestorer(
        word_map=word_map,
        detection_threshold=settings.diacritic_detection_threshold,
        min_text_length=settings.diacritic_min_text_length,
        bigram_freq=bigram_freq,
        context_phrases=context_phrases,
    ) if (settings.diacritic_auto_detect and word_map) else None
    assert restorer is not None, "restorer required for this diagnosis"
    service = LiveNormalizerService(
        settings, pipeline.pending_service, diacritic_restorer=restorer,
        semantic_verifier=None,
    )

    live_data = pipeline.pending_service.get_live_normalization_data(
        domain="general", user_id=None)
    abbreviations = live_data.abbreviations
    known_words = live_data.dictionary_words
    approved_details = live_data.approved_details
    phrase_index = service._build_phrase_index(live_data)
    print(f"{TAG} abbr={len(abbreviations)} known_words={len(known_words)} "
          f"approved_details={len(approved_details)} phrase_index={len(phrase_index)} "
          f"max_ngram={phrase_index.max_ngram} "
          f"bigram={len(bigram_freq)} ctx_phrases={len(context_phrases)} "
          f"word_map={len(word_map)}")

    # ------------------------------------------------------------------
    # Layer passes (mirroring _normalize_live_uncached, minus the layer)
    # ------------------------------------------------------------------

    def spelling_pass(text: str) -> str:
        return apply_known_spelling(text, str(settings.data_dir))[0]

    def phrase_pass(text: str) -> tuple[str, object]:
        res = pipeline.phrase_normalizer.normalize_phrases(
            text, phrase_index, known_words=known_words,
            approved_abbreviations=abbreviations, domain="general")
        tokens = res.tokens
        out = [res.token_replacements.get(i, tok) if i in res.consumed_token_indices else tok
               for i, tok in enumerate(tokens)]
        layout = capture_token_layout(text)
        same = layout.tokens == tokens
        joined = join_scan_tokens(
            out, separators=layout.separators if same else None,
            prefix=layout.prefix if same else "",
            suffix=layout.suffix if same else "")
        return joined, res

    def abbr_pass(text: str) -> str:
        tokens = tokenize_for_scan(text)
        layout = capture_token_layout(text)
        out: list[str] = []
        for tok in tokens:
            if not tok.isalpha():
                out.append(tok)
                continue
            t = normalize_elongated_word(tok, known_words, abbreviations.keys())
            approved = approved_details.get(t.lower())
            if approved:
                alts = list(approved.get("alternative_expansions", []))
                # mirror live: single meaning -> expand, ambiguous -> keep token
                out.append(approved["expanded"] if not alts else tok)
                continue
            out.append(expand_abbreviation(t, abbreviations))
        same = layout.tokens == tokens
        return join_scan_tokens(
            out, separators=layout.separators if same else None,
            prefix=layout.prefix if same else "",
            suffix=layout.suffix if same else "")

    def word_map_cands(text: str) -> str:
        parts = []
        for raw in text.split():
            s = raw.lower().strip(".,!?;:\"'()[]{}…")
            cands = word_map.get(s)
            parts.append(f"{s}->{cands}" if cands else f"{s}->(none)")
        return " ".join(parts)

    # ==================================================================
    # EXPERIMENT 1: small inputs a-i, each layer directly
    # ==================================================================
    print("\n" + "=" * 78)
    print("EXPERIMENT 1 — per-layer on small inputs")
    print("=" * 78)
    cases = [
        ("a1", "su kiên"),
        ("a2", "su kiên nhẫn"),
        ("b", "mo vo ra va tap trung"),
        ("c", "roi chon viec nho nhat"),
        ("d", "ngoi vao ban"),
        ("e", "lich san"),
        ("f", "tien tro"),
        ("g", "dau da qua tai"),
        ("h", "song kho khan"),
        ("i", "tam trang"),
    ]
    for key, text in cases:
        r = restorer.restore(text)
        p_out, p_res = phrase_pass(r.restored_text)
        p_raw, _ = phrase_pass(text)
        a_out = abbr_pass(r.restored_text)
        print(f"\n--- ({key}) input: {text!r}")
        print(f"  L1 restorer : {r.restored_text!r}  applied={r.applied} changes={r.changed_tokens}")
        print(f"  L2 phrase(on L1): {p_out!r}  matches={[(m.matched_phrase, m.expanded) for m in p_res.phrase_matches]}")
        print(f"  L2 phrase(raw)  : {p_raw!r}")
        print(f"  L3 abbr(on L1)  : {a_out!r}")
        print(f"  word_map        : {word_map_cands(text)}")

    # --- (a) mechanism deep-dive -------------------------------------
    print("\n--- (a) mechanism: context-phrase folding in DiacriticRestorer")
    folded_key = tuple(fold(t) for t in ("su", "kien"))
    print(f"  folded key ('su','kien') in context_phrases: "
          f"{folded_key in context_phrases} -> {context_phrases.get(folded_key)}")
    ov = _context_phrase_overrides(["su", "kiên"], context_phrases)
    print(f"  _context_phrase_overrides(['su','kiên']) = {ov}")
    ov2 = _context_phrase_overrides(["su", "kiên", "nhẫn"], context_phrases)
    print(f"  _context_phrase_overrides(['su','kiên','nhẫn']) = {ov2}")
    alpha = [(0, "su"), (1, "kiên")]
    spans = phrase_index.scan(alpha)
    print(f"  PhraseIndex.scan(['su','kiên']) = {[(s.matched_phrase, s.expanded) for s in spans]}")
    # is 'su kien' present in the live PHRASE index sources?
    for name in ("phrase_overrides", "db_phrases", "mined_phrases"):
        mapping = getattr(live_data, name, {}) or {}
        hit = {k: v for k, v in mapping.items() if fold(k) == "su kien"}
        print(f"  live_data.{name} contains 'su kien': {bool(hit)} {hit if hit else ''}")

    # ==================================================================
    # EXPERIMENT 3: full pipeline on Test2 paragraphs + attribution
    # ==================================================================
    print("\n" + "=" * 78)
    print("EXPERIMENT 3 — full pipeline on Test2.txt paragraphs + layer attribution")
    print("=" * 78)
    with open(os.path.join(HERE, "Test2.txt"), encoding="utf-8") as fh:
        raw = fh.read()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    print(f"{TAG} paragraphs found: {len(paragraphs)}")

    layer_outputs = []  # per paragraph dict
    for i, para in enumerate(paragraphs, 1):
        full = service.normalize_live(para, input_method="paste")
        l0 = spelling_pass(para)
        l1 = restorer.restore(para).restored_text
        l2, p_res = phrase_pass(para)
        l3 = abbr_pass(para)
        layer_outputs.append({
            "para": para, "full": full.primary_output, "l0": l0, "l1": l1,
            "l2": l2, "l3": l3,
            "diac_changes": list(full.diacritic_changes),
            "phrase_matches": [(m.matched_phrase, m.expanded, m.source)
                               for m in full.phrase_matches],
        })
        print(f"\n--- Paragraph {i} ({len(para.split())} words)")
        print(f"  FULL : {full.primary_output}")
        print(f"  L1   : {l1}")
        print(f"  L2(raw): {l2}")
        print(f"  L3(raw): {l3}")
        print(f"  diacritic_changes: {full.diacritic_changes}")
        print(f"  phrase_matches   : {layer_outputs[-1]['phrase_matches']}")

    # ==================================================================
    # CHECKLIST: 63 positions from the user's answer key
    # (correct, wrong) — wrong='' means only 'missing' is detectable
    # ==================================================================
    checklist = [
        ("thì đơn giản", "thi đơn giản"),
        ("sự kiên nhẫn", "sự kiện nhẫn"),
        ("tâm trạng ngồi vào bàn", "tầm trang"),
        ("tâm trạng ngồi vào bàn", "vào bán"),
        ("mở vở ra", "mở vợ ra"),
        ("lịch sẵn", "lịch sản"),
        ("tiền trọ", "tiên trợ"),
        ("mệt quá", "met quá"),
        ("nằm im", "nam im"),
        ("kéo chân qua đầu", "qua đấu"),
        ("quá tải", "quá tái"),
        ("nhưng ngồi 4 tiếng", "nhung ngồi"),
        ("nhìn bài", "nhìn bãi"),
        ("làm 3 bài", "làm 3 bai"),
        ("chưa hiểu", "chưa hiệu"),
        ("nước nhỏ rơi liên tục", "nước nhớ rơi"),
        ("cả hòn đá cứng", "hòn đã cùng"),
        ("thật hoành tráng", "that hoanh trang"),
        ("mua vở đẹp", "mua vợ đẹp"),
        ("ít phần nhưng dễ làm", "ít phận"),
        ("ít phần nhưng dễ làm", "để làm"),
        ("ít đồ gây xao nhãng", "ít do"),
        ("mấy suy nghĩ", "máy suy"),
        ("giỏi quá", "giới quá"),
        ("nghe đau đầu ghê", "nghề đau đầu"),
        ("chọn việc nhỏ nhất", "chôn việc"),
        ("mục lục", "mục luc"),
        ("gạch chân", "gạch chan"),
        ("làm thử 1 bài dễ", "làm để 1 bai"),
        ("hỏi thầy cô", "hỏi hội"),
        ("1 chút lười", "chút lưới"),
        ("làm xong một bài tập dài", "lầm xong"),
        ("làm xong một bài tập dài", "bài tập đại"),
        ("phòng ở rối", "phòng ở roi"),
        ("dây đàn", "dây dân"),
        ("bung xả", "bung xóa"),
        ("vòng lặp", "vòng lap"),
        ("dậy trễ", "dạy trẻ"),
        ("phòng nằm", "phòng nam"),
        ("bài dọn lại", "bài đơn lại"),
        ("tối lại hoảng", "tôi lại hoàng"),
        ("Cái vòng lặp này", "cái vọng"),
        ("khô khan", "khô khăn"),
        ("khung để khỏi rơi", "khủng để"),
        ("khung để khỏi rơi", "khỏi roi"),
        ("dậy cùng một khung giờ", "đây cùng"),
        ("gấp chăn", "gặp chấn"),
        ("dọn bàn 5 phút", "đón bạn"),
        ("Mấy việc này", "May việc"),
        ("nhưng nó", "những nỗ"),
        ("để hỏi", "để hội"),
        ("bị kẹt quá lâu", "kết quá lâu"),
        ("mỗi người", "mới người"),
        ("mặt trái", "mặt trai"),
        ("phù hợp", "phụ hợp"),
        ("ít nhưng chất", "ít những chất"),
        ("không cần đông", "cần động"),
        ("hỏi câu đúng hơn chưa", "hội cầu dừng hơn chữa"),
        ("cuốn vở", "cuốn vợ"),
        ("phòng trọ nóng", "trọ nông"),
        ("vài dòng", "vai động"),
        ("1 môn khó", "1 môn kho"),
        ("ăn đúng bữa", "dùng búa"),
        ("Đời sv", "Đổi sv"),
        ("những tối ngồi học muộn", "nhỏ những tôi"),
        ("những tối ngồi học muộn", "muốn học muộn"),
        ("chạy bài", "cháy bài"),
        ("cố gắng", "có gắng"),
    ]

    print("\n" + "=" * 78)
    print("CHECKLIST — per position status + layer attribution")
    print("=" * 78)
    counts = {"OK": 0, "WRONG": 0, "MISSING": 0}
    wrong_by_layer = {"restorer": 0, "phrase": 0, "abbr": 0, "spelling": 0,
                      "combined/other": 0}
    not_fixed = 0
    rows = []
    for idx, (correct, wrong) in enumerate(checklist, 1):
        # locate which paragraph this position belongs to (fold search)
        para_idx = next((k for k, lo in enumerate(layer_outputs)
                         if fold(correct) in fold(lo["full"])
                         or (wrong and fold(wrong) in fold(lo["full"]))), None)
        best = None
        if para_idx is not None:
            lo = layer_outputs[para_idx]
        else:
            lo = None
        ok_full = bool(lo) and has_word(lo["full"], correct)
        wrong_in_full = bool(lo and wrong and has_word(lo["full"], wrong))
        if ok_full and not wrong_in_full:
            status = "OK"
        elif wrong_in_full:
            status = "WRONG"
        else:
            status = "MISSING"
        counts[status] += 1

        attribution = "-"
        if status != "OK" and lo is not None:
            srcs = [name for name in ("l0", "l1", "l2", "l3")
                    if wrong and has_word(lo[name], wrong)]
            label = {"l0": "spelling", "l1": "restorer", "l2": "phrase", "l3": "abbr"}
            srcs = [label[s] for s in srcs]
            if status == "WRONG":
                if srcs == ["restorer"]:
                    attribution = "restorer"
                elif srcs == ["phrase"]:
                    attribution = "phrase"
                elif srcs == ["abbr"]:
                    attribution = "abbr"
                elif srcs == ["spelling"]:
                    attribution = "spelling"
                elif srcs:
                    attribution = "combined/other (" + ",".join(srcs) + ")"
                else:
                    attribution = "full-only(interaction)"
                wrong_by_layer[attribution.split(" (")[0]] = wrong_by_layer.get(
                    attribution.split(" (")[0], 0) + 1
            else:  # MISSING
                fixed_anywhere = [name for name in ("l1", "l2", "l3")
                                  if has_word(lo[name], correct)]
                if fixed_anywhere:
                    attribution = "layer fixed but pipeline lost: " + ",".join(fixed_anywhere)
                else:
                    attribution = "not-fixed-by-rules (needs AI)"
                not_fixed += 1
        rows.append((idx, correct, wrong, status, attribution,
                     para_idx + 1 if para_idx is not None else None))
        print(f"  {idx:>2}. [{status:^7}] {correct!r:<38} wrong={wrong!r:<22} "
              f"para={para_idx + 1 if para_idx is not None else '?'} attr={attribution}")

    print("\n--- SUMMARY")
    total = len(checklist)
    print(f"  positions checked        : {total}")
    print(f"  OK                       : {counts['OK']} ({counts['OK'] * 100 / total:.0f}%)")
    print(f"  WRONG (rule layer broke) : {counts['WRONG']} ({counts['WRONG'] * 100 / total:.0f}%)")
    print(f"  MISSING (not fixed->AI)  : {counts['MISSING']} ({counts['MISSING'] * 100 / total:.0f}%)")
    print(f"  wrong-by-layer           : {json.dumps(wrong_by_layer, ensure_ascii=False)}")
    print(f"  missing not attributable : {not_fixed}")

    # dump full outputs for offline diffing
    out_path = os.path.join(HERE, "diagnose_layers_outputs.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(layer_outputs, fh, ensure_ascii=False, indent=1)
    print(f"{TAG} layer outputs dumped -> {out_path}")


if __name__ == "__main__":
    main()
