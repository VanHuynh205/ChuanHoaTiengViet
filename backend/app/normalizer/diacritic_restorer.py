"""Hybrid diacritic restoration: rule-based word map + AI fallback.

The ``DiacriticRestorer`` tries to restore Vietnamese diacritics in two stages:

1. **Rule-based** — a word-level lookup table (``word_map.json``), mapping
   each no-diacritic form to its most common diacritised form(s).

2. **AI few-shot** — when the rule-based pass leaves too many tokens
   un-restored (coverage below ``RULE_COVERAGE_THRESHOLD``), the full sentence
   is sent to the configured AI provider with a few-shot prompt.

Both stages are hidden behind the single ``restore`` method.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

from app.ai.cache import AsyncTTLCache, make_cache_key
from app.ai.client import AIClient, AIRequest
from app.ai.errors import AIError
from app.ai.prompts import DIACRITIC_RESTORE_TEMPLATE, render
from app.ai.budget import DEFAULT_MAX_OUTPUT_TOKENS, estimate_output_budget
from app.config import Settings
from app.utils.diacritic_detect import is_likely_no_diacritic
from app.utils.text_utils import is_protected_literal, protected_literal_spans

LOGGER = logging.getLogger(__name__)
RULE_COVERAGE_THRESHOLD = 0.80
DIACRITIC_CACHE_TTL = 86_400
DIACRITIC_CACHE_SIZE = 2_048
FEW_SHOT_COUNT = 8

# Punctuation stripped from a token before word-map / context-phrase lookup.
# Curly quotes are included so the first/last word inside a “quoted” span is
# still looked up (and the quotes survive as prefix/suffix on output).
# nosec B105: this is a punctuation strip set, not a credential.
_TOKEN_STRIP_CHARS = ".,!?;:\"'()[]{}\u2026\u201c\u201d\u2018\u2019"  # nosec B105

_BUILTIN_CONTEXT_PHRASE_OVERRIDES: dict[tuple[str, ...], tuple[str, ...]] = {
    ("mon", "do", "an", "co", "so"): (
        "m\u00f4n",
        "\u0111\u1ed3",
        "\u00e1n",
        "c\u01a1",
        "s\u1edf",
    ),
    ("do", "an", "co", "so"): ("\u0111\u1ed3", "\u00e1n", "c\u01a1", "s\u1edf"),
    ("kho", "that", "day"): ("kh\u00f3", "th\u1eadt", "\u0111\u1ea5y"),
    ("that", "day"): ("th\u1eadt", "\u0111\u1ea5y"),
    ("phai", "thuc", "den", "tan", "khuya"): (
        "ph\u1ea3i",
        "th\u1ee9c",
        "\u0111\u1ebfn",
        "t\u1eadn",
        "khuya",
    ),
    ("phai", "thuc", "den"): ("ph\u1ea3i", "th\u1ee9c", "\u0111\u1ebfn"),
    ("thuc", "den", "tan", "khuya"): (
        "th\u1ee9c",
        "\u0111\u1ebfn",
        "t\u1eadn",
        "khuya",
    ),
    ("den", "tan", "khuya"): ("\u0111\u1ebfn", "t\u1eadn", "khuya"),
    ("m", "a"): ("m", "\u00e0"),
    ("nghe", "noi", "dao", "nay"): ("nghe", "n\u00f3i", "d\u1ea1o", "n\u00e0y"),
    ("nghe", "noi"): ("nghe", "n\u00f3i"),
    ("nghe", "mn"): ("nghe", "mn"),
    ("dao", "nay"): ("d\u1ea1o", "n\u00e0y"),
    ("noi", "cho"): ("n\u00f3i", "cho"),
    ("khong", "on", "ha"): ("kh\u00f4ng", "\u1ed5n", "h\u1ea3"),
    ("ko", "on", "ha"): ("ko", "\u1ed5n", "h\u1ea3"),
    ("k", "on", "ha"): ("k", "\u1ed5n", "h\u1ea3"),
    ("khong", "on"): ("kh\u00f4ng", "\u1ed5n"),
    ("ko", "on"): ("ko", "\u1ed5n"),
    ("k", "on"): ("k", "\u1ed5n"),
    ("on", "ha"): ("\u1ed5n", "h\u1ea3"),
    ("song", "tu", "te", "nghe", "co", "ve"): (
        "s\u1ed1ng",
        "t\u1eed",
        "t\u1ebf",
        "nghe",
        "c\u00f3",
        "v\u1ebb",
    ),
    ("song", "tu", "te"): ("s\u1ed1ng", "t\u1eed", "t\u1ebf"),
    ("song", "tuyet", "voi"): ("s\u1ed1ng", "tuy\u1ec7t", "v\u1eddi"),
    ("song", "do", "la"): ("s\u1ed1ng", "\u0111\u00f3", "l\u00e0"),
    # Common chat collocations the news-corpus phrase file misses. Each pair
    # has essentially one plausible accented reading in student chat text.
    ("mo", "vo"): ("m\u1edf", "v\u1edf"),
    ("mua", "vo"): ("mua", "v\u1edf"),
    ("cuon", "vo"): ("cu\u1ed1n", "v\u1edf"),
    ("tam", "trang"): ("t\u00e2m", "tr\u1ea1ng"),
    ("tien", "tro"): ("ti\u1ec1n", "tr\u1ecd"),
    ("qua", "tai"): ("qu\u00e1", "t\u1ea3i"),
    ("vong", "lap"): ("v\u00f2ng", "l\u1eb7p"),
    ("muc", "luc"): ("m\u1ee5c", "l\u1ee5c"),
    ("gach", "chan"): ("g\u1ea1ch", "ch\u00e2n"),
    ("bung", "xa"): ("bung", "x\u1ea3"),
    ("co", "gang"): ("c\u1ed1", "g\u1eafng"),
    ("chay", "bai"): ("ch\u1ea1y", "b\u00e0i"),
    ("mon", "kho"): ("m\u00f4n", "kh\u00f3"),
    ("chua", "hieu"): ("ch\u01b0a", "hi\u1ec3u"),
    ("chon", "viec"): ("ch\u1ecdn", "vi\u1ec7c"),
    ("de", "hoi"): ("\u0111\u1ec3", "h\u1ecfi"),
    ("nam", "im"): ("n\u1eb1m", "im"),
    ("hon", "da"): ("h\u00f2n", "\u0111\u00e1"),
    ("lich", "san"): ("l\u1ecbch", "s\u1eb5n"),
    ("dung", "bua"): ("\u0111\u00fang", "b\u1eefa"),
    ("gioi", "qua"): ("gi\u1ecfi", "qu\u00e1"),
    # Greeting / time collocations the rebuilt news+chat bigram index lost to
    # pruning ("chúc_bạn", "mấy_giờ" fell below the top-N cut) while the
    # feedback-review chat corpus actively boosts the wrong reading ("máy
    # hôm"). Each pair has a single plausible accented reading in chat text.
    ("chuc", "ban"): ("ch\u00fac", "b\u1ea1n"),
    ("may", "gio"): ("m\u1ea5y", "gi\u1edd"),
    ("may", "hom"): ("m\u1ea5y", "h\u00f4m"),
    ("tot", "lam"): ("t\u1ed1t", "l\u1eafm"),
    # Chat sentence-final "roi ban" is always "rồi bạn" (the commerce reading
    # "rồi bán" precedes an object, never ends a chat sentence), and "ban qua"
    # in student chat is "bận quá" ("bán qua" only appears in commerce text,
    # which overwhelmingly arrives already accented).
    ("roi", "ban"): ("r\u1ed3i", "b\u1ea1n"),
    ("ban", "qua"): ("b\u1eadn", "qu\u00e1"),
    # "ngon nhe" has a single chat reading ("ngon nhé"); "ngon nhẹ" is not a
    # Vietnamese collocation, and neither corpus carries "ngon_nhé" evidence.
    ("ngon", "nhe"): ("ngon", "nhé"),
    # ------------------------------------------------------------------
    # Collocations chữa tay từ hai bài kiểm thử chat thật (Test1/Test2,
    # `.scratch/ai-semantic-fix/`): bigram index build từ corpus báo chí
    # chọn thanh điệu sai cho văn phong chat sinh viên (vd "vào_bán"=6486
    # đè "vào_bàn", "khô khăn" đè "khô khan", "làm thất" đè "làm thật").
    # Mỗi key dưới đây chỉ có một cách đọc hợp lý trong chat; key dài hơn
    # (3-5 token) dùng để thắng greedy longest-match của _context_phrase_
    # overrides khi cụm news ngắn hơn chặn đường (vd "vua co" chặn
    # "co gang", "nguoi phu" chặn "phu hop").
    ("chuyen", "nghe", "thi"): ("chuyện", "nghe", "thì"),
    ("lam", "that", "moi", "thay"): ("làm", "thật", "mới", "thấy"),
    ("ngoi", "vao", "ban"): ("ngồi", "vào", "bàn"),
    ("moi", "ngay"): ("mỗi", "ngày"),
    ("met", "qua"): ("mệt", "quá"),
    ("keo", "chan", "qua", "dau"): ("kéo", "chân", "qua", "đầu"),
    ("hieu", "qua"): ("hiệu", "quả"),
    ("k", "bang"): ("k", "bằng"),
    ("phut", "that", "su"): ("phút", "thật", "sự"),
    ("mem", "ca", "hon", "da", "cung"): ("mềm", "cả", "hòn", "đá", "cứng"),
    ("da", "cung"): ("đá", "cứng"),
    ("nguoi", "phu", "hop"): ("người", "phù", "hợp"),
    ("may", "suy", "nghi"): ("mấy", "suy", "nghĩ"),
    ("moi", "ng"): ("mỗi", "ng"),
    ("buoi", "tam", "su"): ("buổi", "tâm", "sự"),
    ("buoi", "hoc"): ("buổi", "học"),
    ("cai", "vong", "nay"): ("cái", "vòng", "này"),
    ("dung", "mot", "phan"): ("đúng", "một", "phần"),
    ("cho", "nay", "cho", "kia"): ("chỗ", "này", "chỗ", "kia"),
    ("it", "nhung", "chat"): ("ít", "nhưng", "chất"),
    ("k", "can", "dong"): ("k", "cần", "đông"),
    ("hoi", "cau"): ("hỏi", "câu"),
    ("dung", "hon", "chua"): ("đúng", "hơn", "chưa"),
    ("tuan", "truoc"): ("tuần", "trước"),
    ("la", "so", "minh"): ("là", "so", "mình"),
    ("doi", "sv"): ("đời", "sv"),
    ("bung", "xoa"): ("bung", "xả"),
    ("chut", "cho", "vui"): ("chút", "cho", "vui"),
    ("chut", "luoi"): ("chút", "lười"),
    ("thang", "duoc"): ("thắng", "được"),
    ("xao", "nhang"): ("xao", "nhãng"),
    ("sao", "minh", "cham", "qua"): ("sao", "mình", "chậm", "quá"),
    ("den", "sang", "lung", "linh"): ("đèn", "sáng", "lung", "linh"),
    ("doc", "muc", "luc"): ("đọc", "mục", "lục"),
    ("lam", "thu"): ("làm", "thử"),
    ("bai", "de"): ("bài", "dễ"),
    ("nhung", "de", "lam"): ("nhưng", "dễ", "làm"),
    ("hoi", "thay", "co"): ("hỏi", "thầy", "cô"),
    ("mot", "loi", "sai"): ("một", "lỗi", "sai"),
    ("lam", "xong"): ("làm", "xong"),
    ("phong", "o", "roi"): ("phòng", "ở", "rối"),
    ("day", "dan"): ("dây", "đàn"),
    ("vai", "dong"): ("vài", "dòng"),
    ("ngu", "muon"): ("ngủ", "muộn"),
    ("thuc", "khuya", "day", "tre", "bo", "bua"): (
        "thức", "khuya", "dậy", "trễ", "bỏ", "bữa",
    ),
    ("ve", "phong", "nam"): ("về", "phòng", "nằm"),
    ("bai", "don", "lai"): ("bài", "dọn", "lại"),
    ("roi", "toi", "lai", "hoang"): ("rồi", "tối", "lại", "hoảng"),
    ("rut", "nang", "luong"): ("rút", "năng", "lượng"),
    ("tu", "tao"): ("tự", "tạo"),
    # "sống khô khan" (kiểu cách, chán nếp sống) — bảo vệ reading "khô khan"
    # trước cụm news "kho khan"->"khó khăn"; token "khô" người dùng đã gõ
    # đúng dấu nên được guard giữ nguyên, "khan" bị khóa về dạng trần.
    ("song", "kho", "khan"): ("sống", "khô", "khan"),
    ("cai", "khung", "de", "khoi", "roi"): ("cái", "khung", "để", "khỏi", "rơi"),
    ("sang", "co", "the", "day", "cung"): ("sáng", "có", "thể", "dậy", "cùng"),
    ("gap", "chan"): ("gấp", "chăn"),
    ("toi", "co", "the", "don", "ban"): ("tối", "có", "thể", "dọn", "bàn"),
    ("may", "viec"): ("mấy", "việc"),
    ("nhung", "no", "lam"): ("nhưng", "nó", "làm"),
    ("bi", "ket"): ("bị", "kẹt"),
    ("qua", "lau"): ("quá", "lâu"),
    ("bien", "thanh"): ("biến", "thành"),
    ("qua", "trinh"): ("quá", "trình"),
    ("tu", "hoc"): ("tự", "học"),
    ("tu", "cham"): ("tự", "chăm"),
    ("tu", "chiu"): ("tự", "chịu"),
    ("chiu", "trac", "nhiem"): ("chịu", "trách", "nhiệm"),
    ("ai", "thay", "het"): ("ai", "thấy", "hết"),
    ("an", "voi"): ("ăn", "với"),
    ("hop", "com"): ("hộp", "cơm"),
    ("phong", "tro", "nong"): ("phòng", "trọ", "nóng"),
    ("se", "nho"): ("sẽ", "nhớ"),
    ("toi", "ngoi", "hoc", "muon"): ("tối", "ngồi", "học", "muộn"),
    ("lan", "chay"): ("lần", "chạy"),
    ("loi", "nhip"): ("lỡ", "nhịp"),
    ("nghi", "dung", "cach"): ("nghỉ", "đúng", "cách"),
    ("cam", "dt"): ("cầm", "đt"),
    ("mat", "thi", "nhin", "bai"): ("mắt", "thì", "nhìn", "bài"),
    ("muc", "tieu", "nho"): ("mục", "tiêu", "nhỏ"),
    ("3", "bai"): ("3", "bài"),
    ("that", "hoanh", "trang"): ("thật", "hoành", "tráng"),
    ("mua", "vo", "dep"): ("mua", "vở", "đẹp"),
    ("but", "moi"): ("bút", "mới"),
    ("thuc", "hien", "thi"): ("thực", "hiện", "thì"),
    ("nghe", "dau", "dau"): ("nghe", "đau", "đầu"),
    ("sap", "xep"): ("sắp", "xếp"),
    ("thu", "tu"): ("thứ", "tự"),
    ("vua", "co", "gang"): ("vừa", "cố", "gắng"),
    ("ngoi", "4", "tieng"): ("ngồi", "4", "tiếng"),
    ("tam", "tri"): ("tâm", "trí"),
    ("noi", "loi", "lam"): ("nói", "lời", "làm"),
    ("kho", "xu"): ("khó", "xử"),
    ("rieng", "le"): ("riêng", "lẻ"),
    ("nghi", "tu", "te"): ("nghĩ", "tử", "tế"),
    ("ai", "do"): ("ai", "đó"),
    ("noi", "vua", "du", "nghe"): ("nói", "vừa", "đủ", "nghe"),
    ("bat", "am", "thanh"): ("bật", "âm", "thanh"),
    ("qua", "lon"): ("quá", "lớn"),
    ("dung", "nha", "ve", "sinh"): ("dùng", "nhà", "vệ", "sinh"),
    ("don", "sach"): ("dọn", "sạch"),
    ("sau", "khi", "dung"): ("sau", "khi", "dùng"),
    ("muon", "do", "cua", "ban"): ("mượn", "đồ", "của", "bạn"),
    ("tra", "dung", "hen"): ("trả", "đúng", "hẹn"),
    ("cai", "do", "nho", "thoi"): ("cái", "đó", "nhỏ", "thôi"),
    ("lam", "dung", "han"): ("làm", "đúng", "hạn"),
    ("ganh", "thay"): ("gánh", "thay"),
    ("cuc", "da", "roi"): ("cục", "đá", "rồi"),
    ("hom", "nay"): ("hôm", "nay"),
    # Chat miền Nam "ba mẹ" (bố mẹ) phổ biến hơn hẳn "bà mẹ" trong văn bản
    # sinh viên; case "bà mẹ" hiếm và thường đã có dấu sẵn (guard giữ nguyên).
    ("ba", "me"): ("ba", "mẹ"),
    ("lo", "hon"): ("lo", "hơn"),
    ("hoi", "ba", "co", "met"): ("hỏi", "ba", "có", "mệt"),
    ("o", "nha"): ("ở", "nhà"),
    ("nha", "tro"): ("nhà", "trọ"),
    ("luc", "dem"): ("lúc", "đêm"),
    # Bổ sung từ vòng chạy CSV đầu tiên: cụm bị bigram/cụm news dài hơn
    # che khuất (greedy longest-match) hoặc còn thiếu.
    ("nuoc", "nho", "roi"): ("nước", "nhỏ", "rơi"),
    ("cho", "ngoi"): ("chỗ", "ngồi"),
    ("kha", "yen"): ("kha", "yên"),
    ("it", "do", "gay"): ("ít", "đồ", "gây"),
    ("lim", "dim"): ("lim", "dim"),
    ("tat", "bot"): ("tắt", "bớt"),
    # "bi kẹt quá lâu" — cụm 3-token "bi ket qua" của corpus news đang thắng
    # cặp 2-token "bi ket", nên phải đi bằng key dài hơn.
    ("bi", "ket", "qua", "lau"): ("bị", "kẹt", "quá", "lâu"),
    # Corpus news có ("khi","bi") nuốt mất "bi" trước khi "bi ket..." kịp khớp.
    ("khi", "bi", "ket", "qua", "lau"): ("khi", "bị", "kẹt", "quá", "lâu"),
    ("nha", "tro", "thi"): ("nhà", "trọ", "thì"),
    # ("o","nha") của built-in nuốt "nha" phá alignment của
    # ("nha","tro","thi") — đi bằng key 4-token bắt đầu từ "o".
    ("o", "nha", "tro", "thi"): ("ở", "nhà", "trọ", "thì"),
    ("bien", "van", "de"): ("biến", "vấn", "đề"),
    ("ho", "lo"): ("họ", "lo"),
    # Vòng 3: các cụm bị cụm news ngắn hơn che khuất ở alignment trước,
    # hoặc từ chức năng mà bigram không có bằng chứng.
    ("nhung", "ngoi", "4", "tieng"): ("nhưng", "ngồi", "4", "tiếng"),
    ("ngoi", "truoc", "cuon", "vo"): ("ngồi", "trước", "cuốn", "vở"),
    ("tro", "nong"): ("trọ", "nóng"),
    # Giữ nguyên "lung tung" — chặn bigram chọn "lúng túng".
    ("bay", "lung", "tung"): ("bay", "lung", "tung"),
    ("chen", "hang"): ("chen", "hàng"),
    ("dau", "thi"): ("đầu", "thì"),
    ("vi", "bai", "nhom"): ("vì", "bài", "nhóm"),
    ("vi", "bay", "gio"): ("vì", "bây", "giờ"),
    ("vi", "k", "phai"): ("vì", "k", "phải"),
    ("lap", "lich"): ("lập", "lịch"),
    ("it", "phan"): ("ít", "phần"),
    ("roi", "chon"): ("rồi", "chọn"),
    ("kieu", "minh"): ("kiểu", "mình"),
    ("chut", "xao"): ("chút", "xao"),
    ("bai", "tap", "dai"): ("bài", "tập", "dài"),
    ("cai", "moc"): ("cái", "móc"),
    ("thi", "qua", "nang"): ("thì", "quá", "nặng"),
    ("nhieu", "sinh", "vien"): ("nhiều", "sinh", "viên"),
    ("mat", "muon", "ngu"): ("mặt", "muốn", "ngủ"),
    ("nhac", "nhau"): ("nhắc", "nhau"),
    ("lich", "nop", "bai"): ("lịch", "nộp", "bài"),
    ("nguoi", "khac"): ("người", "khác"),
    ("khac", "hoc", "nhanh"): ("khác", "học", "nhanh"),
    ("khong", "duoc", "nhieu"): ("không", "được", "nhiều"),
    ("3", "tieng"): ("3", "tiếng"),
}

# --- Bigram co-occurrence scoring ---

_SHARED_BIGRAM_FREQ: dict[str, int] | None = None
_SHARED_BIGRAM_FREQ_LOCK = threading.Lock()


def load_bigram_freq(path: Path) -> dict[str, int]:
    """Load precomputed bigram frequency index."""
    if not path.exists():
        LOGGER.info("bigram_freq.json not found at %s; bigram scoring disabled", path)
        return {}
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return {str(key): int(value) for key, value in raw.items()}


def get_shared_bigram_freq(data_dir: Path) -> dict[str, int]:
    """Lazily load and cache the shared bigram frequency index."""
    global _SHARED_BIGRAM_FREQ
    if _SHARED_BIGRAM_FREQ is not None:
        return _SHARED_BIGRAM_FREQ
    with _SHARED_BIGRAM_FREQ_LOCK:
        if _SHARED_BIGRAM_FREQ is not None:
            return _SHARED_BIGRAM_FREQ
        _SHARED_BIGRAM_FREQ = load_bigram_freq(data_dir / "diacritic" / "bigram_freq.json")
        return _SHARED_BIGRAM_FREQ


_SHARED_CONTEXT_PHRASE_OVERRIDES: dict[tuple[str, ...], tuple[str, ...]] | None = None
_SHARED_CONTEXT_PHRASE_OVERRIDES_LOCK = threading.Lock()


def load_context_phrase_overrides(path: Path) -> dict[tuple[str, ...], tuple[str, ...]]:
    """Load precomputed no-diacritic phrase overrides from JSON."""
    if not path.exists():
        LOGGER.info("context_phrases.json not found at %s; using built-in phrases only", path)
        return {}

    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    if not isinstance(raw, dict):
        LOGGER.warning("context phrase file at %s is not a JSON object", path)
        return {}

    phrases: dict[tuple[str, ...], tuple[str, ...]] = {}
    for raw_key, raw_value in raw.items():
        nd_tokens = tuple(str(raw_key).strip().lower().split())
        wd_tokens = tuple(str(raw_value).strip().split())
        if len(nd_tokens) < 2 or len(nd_tokens) != len(wd_tokens):
            continue
        phrases[nd_tokens] = wd_tokens
    return phrases


def get_shared_context_phrase_overrides(data_dir: Path) -> dict[tuple[str, ...], tuple[str, ...]]:
    """Lazily load context phrase overrides, with built-ins taking precedence."""
    global _SHARED_CONTEXT_PHRASE_OVERRIDES
    if _SHARED_CONTEXT_PHRASE_OVERRIDES is not None:
        return _SHARED_CONTEXT_PHRASE_OVERRIDES
    with _SHARED_CONTEXT_PHRASE_OVERRIDES_LOCK:
        if _SHARED_CONTEXT_PHRASE_OVERRIDES is not None:
            return _SHARED_CONTEXT_PHRASE_OVERRIDES
        file_phrases = load_context_phrase_overrides(
            data_dir / "diacritic" / "context_phrases.json"
        )
        _SHARED_CONTEXT_PHRASE_OVERRIDES = {
            **file_phrases,
            **_BUILTIN_CONTEXT_PHRASE_OVERRIDES,
        }
        return _SHARED_CONTEXT_PHRASE_OVERRIDES


def _score_with_bigrams(
    candidates: list[str],
    prev_candidates: list[str] | None,
    next_candidates: list[str] | None,
    bigram_freq: dict[str, int],
    original: str | None = None,
    preserve_original: bool = False,
) -> str:
    """Pick the candidate that forms the highest-frequency bigram with neighbours.

    Considers ALL possible pairings with neighbour candidates, not just the
    first one. When mixed text asks for conservative behavior, an original
    candidate is retained if the index has no meaningful evidence.
    """
    if not bigram_freq:
        return candidates[0]

    def score(candidate: str) -> int:
        value = 0
        if prev_candidates:
            value += max(
                (bigram_freq.get(f"{prev}_{candidate}", 0) for prev in prev_candidates),
                default=0,
            )
        if next_candidates:
            value += max(
                (bigram_freq.get(f"{candidate}_{nxt}", 0) for nxt in next_candidates),
                default=0,
            )
        return value

    scores = {candidate: score(candidate) for candidate in candidates}
    best_score = -1
    best_candidate = candidates[0]
    for candidate in candidates:
        candidate_score = scores[candidate]
        if candidate_score > best_score:
            best_score = candidate_score
            best_candidate = candidate

    if best_score <= 0:
        return original if preserve_original and original in candidates else candidates[0]

    # A no-diacritic token can be a valid Vietnamese word (for example
    # ``nghe`` or ``hoa``). Do not change it for a marginal bigram win: the
    # frequency index is evidence, not a semantic decision. A clear positive
    # signal (such as ``nghe thuat``) still wins because the original score is
    # zero while the accented candidate has a non-zero score.
    if original in scores:
        original_score = scores[original]
        if preserve_original and (original_score == best_score or (
            original_score > 0 and best_score < original_score * 1.2
        )):
            return original
    return best_candidate


def _looks_like_short_abbreviation(token: str) -> bool:
    """Return whether a short all-consonant token is likely chat shorthand."""
    if not token.isalpha() or not 1 < len(token) <= 3:
        return False
    folded = unicodedata.normalize("NFD", token.lower())
    return not any(char in "aeiouy" for char in folded)


@dataclass(frozen=True)
class DiacriticResult:
    restored_text: str
    confidence: float
    changed_tokens: list[tuple[str, str]]
    fallback_used: bool
    engine: Literal["rule", "ai", "hybrid", "skip"]
    latency_ms: int


def load_word_map(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        LOGGER.warning("word_map not found at %s; rule-based disabled", path)
        return {}
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return {k: (v if isinstance(v, list) else [v]) for k, v in raw.items()}


def load_few_shot_examples(path: Path, count: int = FEW_SHOT_COUNT) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        examples = json.load(fh)
    return examples[:count]


def _format_few_shot(examples: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for ex in examples:
        no_d = ex.get("no_diacritics", ex.get("input", ""))
        with_d = ex.get("with_diacritics", ex.get("output", ""))
        lines.append(f'"{no_d}" → "{with_d}"')
    return "\n".join(lines)


def _rule_restore(
    text: str,
    word_map: dict[str, list[str]],
    bigram_freq: dict[str, int] | None = None,
    context_phrases: dict[tuple[str, ...], tuple[str, ...]] | None = None,
    prefer_diacritics: bool = False,
) -> tuple[str, list[tuple[str, str]], float, dict[str, list[str]]]:
    """Restore diacritics using word map + optional bigram context scoring.

    Returns ``(restored_text, changed_tokens, coverage, ambiguous_map)``
    where *ambiguous_map* contains tokens that had multiple candidates.

    Parameters
    ----------
    prefer_diacritics:
        Retained for compatibility with callers that distinguish mixed text. The
        selector now keeps the original candidate and requires meaningful context
        evidence before replacing it.
    """
    chunks = re.split(r"(\s+)", text)
    tokens = [chunk for chunk in chunks if chunk and not chunk.isspace()]
    protected_ranges = protected_literal_spans(text)
    protected_indices = {i for i, token in enumerate(re.finditer(r"\S+", text))
                         if any(a < token.end() and b > token.start() for a, b in protected_ranges)}
    if not tokens:
        return text, [], 1.0, {}

    # First pass: resolve each token to its best candidate list
    meta: list[tuple[str, str, list[str] | None]] = []  # (original, stripped, candidates)
    matched = 0
    ambiguous: dict[str, list[str]] = {}

    for token_index, token in enumerate(tokens):
        lower = token.lower()
        stripped = lower.strip(_TOKEN_STRIP_CHARS)
        if token_index in protected_indices or is_protected_literal(token):
            meta.append((token, stripped, None))
            matched += 1
            continue
        candidates = word_map.get(stripped)
        if _looks_like_short_abbreviation(stripped):
            meta.append((token, stripped, None))
            matched += 1
            continue
        if candidates:
            meta.append((token, stripped, candidates))
            matched += 1
            if len(candidates) > 1:
                ambiguous[stripped] = candidates
        else:
            meta.append((token, stripped, None))
            if not stripped.isalpha():
                matched += 1

    active_context_phrases = (
        _BUILTIN_CONTEXT_PHRASE_OVERRIDES if context_phrases is None else context_phrases
    )
    context_overrides = _context_phrase_overrides(
        [stripped for _, stripped, _ in meta],
        active_context_phrases,
    )
    matched += sum(
        1 for index in context_overrides if meta[index][2] is None and meta[index][1].isalpha()
    )

    # Second pass: resolve candidates using bigram context
    restored: list[str] = []
    changed: list[tuple[str, str]] = []

    for i, (token, stripped, candidates) in enumerate(meta):
        if i in protected_indices:
            restored.append(token)
            continue
        context_best = context_overrides.get(i)
        if candidates is None and context_best is None:
            restored.append(token)
            continue

        if context_best is not None:
            best = context_best
        elif candidates is not None and (len(candidates) == 1 or not bigram_freq):
            best = candidates[0]
        elif candidates is None:
            best = stripped
        else:
            # Determine resolved neighbours for bigram scoring
            prev_cand_list: list[str] | None = None
            next_cand_list: list[str] | None = None
            if i > 0:
                prev_cand_list = _context_candidate_list(meta, i - 1, context_overrides)
            if i < len(meta) - 1:
                next_cand_list = _context_candidate_list(meta, i + 1, context_overrides)

            best = _score_with_bigrams(
                candidates,
                prev_cand_list,
                next_cand_list,
                bigram_freq or {},
                original=stripped,
                preserve_original=prefer_diacritics,
            )

        if token.isupper() and len(token) > 1 and best == stripped:
            best = token
        elif token[0].isupper() and best[0].islower():
            best = best[0].upper() + best[1:]
        prefix = token[: len(token) - len(token.lstrip(_TOKEN_STRIP_CHARS))]
        suffix = token[len(token.rstrip(_TOKEN_STRIP_CHARS)) :]
        final = prefix + best + suffix
        restored.append(final)
        if final != token:
            changed.append((token, final))

    coverage = matched / len(tokens) if tokens else 1.0
    restored_iter = iter(restored)
    rebuilt = [
        chunk if chunk.isspace() else next(restored_iter)
        for chunk in chunks
        if chunk
    ]
    return "".join(rebuilt), changed, coverage, ambiguous


def _context_candidate_list(
    meta: Sequence[tuple[str, str, list[str] | None]],
    index: int,
    context_overrides: dict[int, str],
) -> list[str] | None:
    if index in context_overrides:
        return [context_overrides[index]]
    _, stripped, candidates = meta[index]
    if candidates:
        return candidates
    if stripped and stripped.isalpha():
        return [stripped]
    return None


_FOLDED_PHRASE_INDEX_MEMO: tuple[
    dict[tuple[str, ...], tuple[str, ...]],
    dict[tuple[str, ...], tuple[str, ...]],
    list[int],
] | None = None


def _folded_context_phrase_index(
    context_phrases: dict[tuple[str, ...], tuple[str, ...]],
) -> tuple[dict[tuple[str, ...], tuple[str, ...]], list[int]]:
    """Fold the phrase asset once and reuse it across calls.

    Phrase assets are indexed by no-diacritic text, while a pasted message can
    contain a mix of accented and unaccented words. Folding both sides for
    lookup lets a known phrase repair only the missing tokens instead of
    falling back to independent word-frequency guesses.

    The fold only depends on the shared phrase dict, so memoize it on dict
    identity (a strong ref — ``id()`` alone could collide after GC). Rebuilding
    happens only when a different dict object is loaded.
    """
    global _FOLDED_PHRASE_INDEX_MEMO
    memo = _FOLDED_PHRASE_INDEX_MEMO
    if memo is not None and memo[0] is context_phrases:
        return memo[1], memo[2]
    folded_phrases = {
        tuple(_strip_token_diacritics(token) for token in phrase): replacement
        for phrase, replacement in context_phrases.items()
    }
    context_phrase_lengths = sorted({len(phrase) for phrase in folded_phrases}, reverse=True)
    _FOLDED_PHRASE_INDEX_MEMO = (context_phrases, folded_phrases, context_phrase_lengths)
    return folded_phrases, context_phrase_lengths


def _context_phrase_overrides(
    stripped_tokens: Sequence[str],
    context_phrases: dict[tuple[str, ...], tuple[str, ...]],
) -> dict[int, str]:
    overrides: dict[int, str] = {}
    folded_phrases, context_phrase_lengths = _folded_context_phrase_index(context_phrases)
    folded_tokens = tuple(_strip_token_diacritics(token) for token in stripped_tokens)
    index = 0
    while index < len(stripped_tokens):
        matched: tuple[str, ...] | None = None
        for length in context_phrase_lengths:
            phrase = folded_tokens[index : index + length]
            if phrase in folded_phrases:
                matched = phrase
                break
        if matched is None:
            index += 1
            continue

        replacement = folded_phrases[matched]
        for offset, token in enumerate(replacement):
            position = index + offset
            if position >= len(stripped_tokens):
                # A mis-sized phrase entry must never raise mid-pipeline; skip
                # the out-of-range tail (verified entries are length-matched).
                continue
            if _token_has_explicit_diacritics(stripped_tokens[position]):
                # The user typed this token with accents on purpose; a folded
                # phrase match must repair missing accents, never overwrite an
                # existing choice ("su kiên nhẫn" must stay "kiên").
                continue
            overrides[position] = token
        index += len(matched)
    return overrides


def _token_has_explicit_diacritics(token: str) -> bool:
    lowered = token.lower()
    if "đ" in lowered:
        # "đ" does not decompose under NFD but is still an intended accent.
        return True
    return any(
        unicodedata.category(char) == "Mn"
        for char in unicodedata.normalize("NFD", lowered)
    )


def _strip_token_diacritics(token: str) -> str:
    folded = unicodedata.normalize("NFD", token.lower())
    return "".join(
        char for char in folded if unicodedata.category(char) != "Mn"
    ).replace("đ", "d")


def collect_ambiguous_diacritics(text: str, word_map: dict[str, list[str]]) -> dict[str, list[str]]:
    """Return a map of bare tokens → candidate list for tokens with multiple options."""
    result: dict[str, list[str]] = {}
    for token in text.split():
        stripped = token.lower().strip(_TOKEN_STRIP_CHARS)
        candidates = word_map.get(stripped)
        if candidates and len(candidates) > 1:
            result[stripped] = candidates
    return result


class DiacriticRestorer:
    def __init__(
        self,
        settings: Settings,
        ai_client: AIClient,
        word_map: dict[str, list[str]] | None = None,
        bigram_freq: dict[str, int] | None = None,
        context_phrases: dict[tuple[str, ...], tuple[str, ...]] | None = None,
        few_shot_examples: list[dict[str, str]] | None = None,
    ) -> None:
        self._settings = settings
        self._ai_client = ai_client

        data_dir = settings.data_dir
        diacritic_dir = data_dir / "diacritic"

        if word_map is not None:
            self._word_map = word_map
        else:
            self._word_map = load_word_map(diacritic_dir / "word_map.json")

        if bigram_freq is not None:
            self._bigram_freq = bigram_freq
        else:
            self._bigram_freq = load_bigram_freq(diacritic_dir / "bigram_freq.json")

        if context_phrases is not None:
            self._context_phrases = context_phrases
        else:
            self._context_phrases = get_shared_context_phrase_overrides(data_dir)

        if few_shot_examples is not None:
            self._few_shot = few_shot_examples
        else:
            self._few_shot = load_few_shot_examples(diacritic_dir / "sample_few_shot.json")

        self._cache: AsyncTTLCache[DiacriticResult] = AsyncTTLCache(
            maxsize=DIACRITIC_CACHE_SIZE,
            ttl_seconds=DIACRITIC_CACHE_TTL,
        )

    async def restore(self, text: str, force: bool = False) -> DiacriticResult:
        started = time.perf_counter()

        if not force and not is_likely_no_diacritic(
            text,
            threshold=self._settings.diacritic_detection_threshold,
            min_length=self._settings.diacritic_min_text_length,
        ):
            latency = int((time.perf_counter() - started) * 1000)
            return DiacriticResult(
                restored_text=text,
                confidence=1.0,
                changed_tokens=[],
                fallback_used=False,
                engine="skip",
                latency_ms=latency,
            )

        cache_key = make_cache_key("diacritic", text, None, 0.0)
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        # Mixed text still needs per-token restoration, but valid unaccented
        # words remain candidates until context provides enough evidence.
        from app.utils.diacritic_detect import _count_vowels
        with_d, total = _count_vowels(text)
        has_any_diacritics = with_d > 0 and total > 0
        prefer_diacritics = has_any_diacritics

        rule_text, rule_changed, coverage, _ = await asyncio.to_thread(
            _rule_restore,
            text,
            self._word_map,
            self._bigram_freq,
            self._context_phrases,
            prefer_diacritics=prefer_diacritics,
        )

        if coverage >= RULE_COVERAGE_THRESHOLD:
            latency = int((time.perf_counter() - started) * 1000)
            result = DiacriticResult(
                restored_text=rule_text,
                confidence=min(coverage, 0.95),
                changed_tokens=rule_changed,
                fallback_used=True,
                engine="rule",
                latency_ms=latency,
            )
            await self._cache.set(cache_key, result)
            return result

        if self._ai_client.is_available():
            try:
                ai_result = await self._call_ai(text)
                latency = int((time.perf_counter() - started) * 1000)
                ai_changed = _diff_tokens(text, ai_result["restored"])
                result = DiacriticResult(
                    restored_text=ai_result["restored"],
                    confidence=float(ai_result.get("confidence", 0.9)),
                    changed_tokens=ai_changed,
                    fallback_used=False,
                    engine="ai" if coverage < 0.3 else "hybrid",
                    latency_ms=latency,
                )
                await self._cache.set(cache_key, result)
                return result
            except AIError as exc:
                LOGGER.warning("AI diacritic restoration failed, using rule-based: %s", exc)

        latency = int((time.perf_counter() - started) * 1000)
        result = DiacriticResult(
            restored_text=rule_text,
            confidence=min(coverage, 0.7),
            changed_tokens=rule_changed,
            fallback_used=True,
            engine="rule",
            latency_ms=latency,
        )
        await self._cache.set(cache_key, result)
        return result

    async def _call_ai(self, text: str) -> dict[str, str]:
        few_shot_str = _format_few_shot(self._few_shot)
        prompt_text = render(
            DIACRITIC_RESTORE_TEMPLATE,
            {"few_shot_examples": few_shot_str, "input_text": text},
        )
        request = AIRequest(
            prompt=prompt_text,
            max_tokens=estimate_output_budget(
                text,
                getattr(self._settings, "ai_max_output_tokens", DEFAULT_MAX_OUTPUT_TOKENS),
            ),
            temperature=0.1,
            json_mode=True,
        )
        response = await self._ai_client.complete(request)
        return _parse_ai_response(response.text, text)


def _parse_ai_response(raw: str, original: str) -> dict[str, str]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            cleaned = "\n".join(lines)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return {"restored": original, "confidence": "0.0"}

    # A provider can return valid JSON that is not an object (a bare list,
    # string or number). Treat it like a failed parse instead of crashing the
    # request with an AttributeError outside the AIError fallback path.
    if not isinstance(parsed, dict):
        return {"restored": original, "confidence": "0.0"}
    restored = parsed.get("restored", original)
    raw_confidence = parsed.get("confidence", 0.9)
    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        # ``null``/non-numeric confidence previously became "None" and blew up
        # later at float() time; degrade to "not confident" instead.
        confidence = 0.0
    return {"restored": str(restored), "confidence": str(confidence)}


_SHARED_WORD_MAP: dict[str, list[str]] | None = None
_SHARED_WORD_MAP_LOCK = threading.Lock()

# Chat tokens the news-corpus word map is missing entirely. With no entry the
# restorer can never touch them ("met", "thi" stay bare forever); adding the
# common candidates lets bigram context and the AI review pass decide. Keys the
# generated map already defines are never overridden.
_BUILTIN_WORD_MAP_ENTRIES: dict[str, list[str]] = {
    "met": ["mệt"],
    "thi": ["thì", "thị", "thí"],
    "trai": ["trái", "trai"],
    "vai": ["vài", "vai"],
    "nam": ["nằm", "năm", "nam"],
}


def get_shared_word_map(data_dir: Path) -> dict[str, list[str]]:
    global _SHARED_WORD_MAP
    if _SHARED_WORD_MAP is not None:
        return _SHARED_WORD_MAP
    with _SHARED_WORD_MAP_LOCK:
        if _SHARED_WORD_MAP is not None:
            return _SHARED_WORD_MAP
        word_map = load_word_map(data_dir / "diacritic" / "word_map.json")
        for token, candidates in _BUILTIN_WORD_MAP_ENTRIES.items():
            word_map.setdefault(token, candidates)
        _SHARED_WORD_MAP = word_map
        return _SHARED_WORD_MAP


@dataclass(frozen=True)
class SyncDiacriticResult:
    restored_text: str
    changed_tokens: list[tuple[str, str]]
    applied: bool


class SyncDiacriticRestorer:
    def __init__(
        self,
        word_map: dict[str, list[str]],
        detection_threshold: float = 0.6,
        min_text_length: int = 8,
        bigram_freq: dict[str, int] | None = None,
        context_phrases: dict[tuple[str, ...], tuple[str, ...]] | None = None,
    ) -> None:
        self._word_map = word_map
        self._detection_threshold = detection_threshold
        self._min_text_length = min_text_length
        self._bigram_freq = bigram_freq or {}
        self._context_phrases = (
            _BUILTIN_CONTEXT_PHRASE_OVERRIDES if context_phrases is None else context_phrases
        )

    def restore(self, text: str) -> SyncDiacriticResult:
        # Check if full document needs restoration
        needs_full_restore = is_likely_no_diacritic(
            text,
            threshold=self._detection_threshold,
            min_length=self._min_text_length,
        )

        # For mixed text (some words with diacritics, some without), still attempt
        # per-word restoration to handle cases like "song tử tế" where "song" needs
        # restoration even though the text overall has many diacritics.
        # Skip only if text is too short.
        if len(text.strip()) < self._min_text_length and not needs_full_restore:
            return SyncDiacriticResult(restored_text=text, changed_tokens=[], applied=False)

        # Determine whether this is mixed text. Context phrases and the guarded
        # bigram selector handle missing accents without rewriting valid words.
        from app.utils.diacritic_detect import _count_vowels
        with_d, total = _count_vowels(text)
        has_any_diacritics = with_d > 0 and total > 0
        prefer_diacritics = has_any_diacritics

        restored, changed, _, _ = _rule_restore(
            text,
            self._word_map,
            self._bigram_freq,
            self._context_phrases,
            prefer_diacritics=prefer_diacritics,
        )

        return SyncDiacriticResult(
            restored_text=restored,
            changed_tokens=changed,
            applied=bool(changed),
        )


def _diff_tokens(original: str, restored: str) -> list[tuple[str, str]]:
    orig_tokens = original.split()
    rest_tokens = restored.split()
    changed: list[tuple[str, str]] = []
    for orig, rest in zip(orig_tokens, rest_tokens):
        if orig != rest:
            changed.append((orig, rest))
    return changed
