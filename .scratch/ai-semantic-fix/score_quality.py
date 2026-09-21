# -*- coding: utf-8 -*-
"""[DEBUG-a4f2] Score normalization quality against known-bad patterns.

Usage:
  ..\\.venv\\Scripts\\python.exe .scratch/ai-semantic-fix/score_quality.py <file.txt>
Counts occurrences of known-wrong forms (from the user's real Test2 output)
and prints an error score. Lower = better.
"""
from __future__ import annotations

import re
import sys
import unicodedata

# (wrong_pattern, description) — literal, case-insensitive, word-ish boundaries
WRONG = [
    (r"sự kiện nhẫn", "sự kiên nhẫn bị phá"),
    (r"tầm trang", "tâm trạng"),
    (r"vào bán", "vào bàn"),
    (r"mở vợ", "mở vở"),
    (r"mua vợ", "mua vở"),
    (r"cuốn vợ", "cuốn vở"),
    (r"lịch sản", "lịch sẵn"),
    (r"tiên trợ", "tiền trọ"),
    (r"\bmet quá", "mệt quá"),
    (r"\bnam im", "nằm im"),
    (r"qua đấu", "qua đầu"),
    (r"quá tái", "quá tải"),
    (r"những ngồi 4", "nhưng ngồi 4"),
    (r"nhìn bãi", "nhìn bài"),
    (r"làm 3 bai\b", "làm 3 bài"),
    (r"chưa hiệu", "chưa hiểu"),
    (r"nước nhớ rồi", "nước nhỏ rơi"),
    (r"ca hòn đã cùng", "cả hòn đá cứng"),
    (r"\bthat hoành tráng", "thật hoành tráng"),
    (r"ít phận nhưng để làm", "ít phần nhưng dễ làm"),
    (r"ít do gây", "ít đồ gây"),
    (r"\bmáy suy nghĩ", "mấy suy nghĩ"),
    (r"giới quá", "giỏi quá"),
    (r"nghề đầu đầu", "nghe đau đầu"),
    (r"\bchôn việc", "chọn việc"),
    (r"\bmục luc\b", "mục lục"),
    (r"gạch chan", "gạch chân"),
    (r"làm thủ 1 bài để", "làm thử 1 bài dễ"),
    (r"cần hội thầy cô", "cần hỏi thầy cô"),
    (r"1 chut lưới", "1 chút lười"),
    (r"\blầm xong", "làm xong"),
    (r"bài tập đại", "bài tập dài"),
    (r"phòng ở roi", "phòng ở rối"),
    (r"dây dân", "dây đàn"),
    (r"bung xóa", "bung xả"),
    (r"vòng lap\b", "vòng lặp"),
    (r"dạy trẻ", "dậy trễ"),
    (r"phòng nam\b", "phòng nằm"),
    (r"bài đơn lại", "bài dọn lại"),
    (r"tôi lại hoàng", "tối lại hoảng"),
    (r"Cái vọng này", "Cái vòng lặp này"),
    (r"khô khăn", "khô khan"),
    (r"cái khủng", "cái khung"),
    (r"khỏi roi\b", "khỏi rơi"),
    (r"đây cũng một khung giờ", "dậy cùng một khung giờ"),
    (r"gặp chấn", "gấp chăn"),
    (r"đón bạn 5 phút", "dọn bàn 5 phút"),
    (r"\bMay việc này", "Mấy việc này"),
    (r"những nỗ ", "nhưng nó "),
    (r"để hội", "để hỏi"),
    (r"kết quá lâu", "kẹt quá lâu"),
    (r"mới người chỉ cần", "mỗi người chỉ cần"),
    (r"mặt trai", "mặt trái"),
    (r"phụ hop\b", "phù hợp"),
    (r"ít những chất", "ít nhưng chất"),
    (r"không cần động", "không cần đông"),
    (r"hội cầu dừng hơn chữa", "hỏi câu đúng hơn chưa"),
    (r"phòng trọ nông", "phòng trọ nóng"),
    (r"\bvai động", "vài dòng"),
    (r"môn kho\b", "môn khó"),
    (r"ăn dùng búa", "ăn đúng bữa"),
    (r"\bĐổi sv\b", "Đời sv"),
    (r"nhỏ những tôi ngồi học muốn", "nhớ những tối ngồi học muộn"),
    (r"cháy bài", "chạy bài"),
    (r"\bcó gắng", "cố gắng"),
]

# "thi" xuất hiện dày đặc trong văn bản này, hầu hết đúng là "thì" — chỉ đếm tham khảo
THI_RE = re.compile(r"(?<![\wđ])thi(?![\wđ])", re.IGNORECASE)


def fold(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", value.casefold())
        if unicodedata.category(c) != "Mn"
    ).replace("đ", "d")


def main() -> None:
    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    total = 0
    for pattern, label in WRONG:
        count = len(re.findall(pattern, text, flags=re.IGNORECASE))
        if count:
            total += count
            print(f"  {count}x  {label}  [{pattern}]")
    thi = len(THI_RE.findall(text))
    print(f"TOTAL wrong-pattern hits: {total}")
    print(f"'thi' standalone occurrences (context-dependent, reference only): {thi}")


if __name__ == "__main__":
    main()
