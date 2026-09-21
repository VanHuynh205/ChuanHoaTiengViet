# -*- coding: utf-8 -*-
"""[DEBUG-a4f2] Compare news vs chat bigram counts to pick ChatWeight."""
from __future__ import annotations

import csv
import json
from collections import Counter

news = json.load(open("data/diacritic/bigram_freq.json", encoding="utf-8"))
chat: Counter[str] = Counter()
for name in ["Dev.csv", "Test.csv", "Train.csv"]:
    with open(f"data/DataDauCau/chat/{name}", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            words = [w.strip(".,!?;:\"()[]{}…").lower() for w in row["with_diacritics"].split()]
            words = [w for w in words if w and w.isalpha()]
            for i in range(len(words) - 1):
                chat[f"{words[i]}_{words[i+1]}"] += 1
print("chat unique bigrams:", len(chat))

keys = ["chúc_bạn", "chức_bán", "bạn_ngủ", "mấy_giờ", "máy_giờ", "rồi_bạn", "rồi_bán",
        "tốt_lắm", "tốt_làm", "vào_bàn", "vào_bán", "mở_vở", "vợ_ra", "lịch_sẵn",
        "tiền_trọ", "quá_tải", "vòng_lặp", "mục_lục", "gạch_chân", "hỏi_câu",
        "hội_cầu", "đúng_bữa", "cố_gắng", "nằm_im", "cần_hỏi", "thật_hoành",
        "nước_nhỏ", "giọt_nước", "hòn_đá", "môn_khó", "ăn_đúng", "dậy_trễ"]
print(f"{'key':14} {'news':>7} {'chat':>6}")
for k in keys:
    print(f"{k:14} {news.get(k, 0):>7} {chat.get(k, 0):>6}")
