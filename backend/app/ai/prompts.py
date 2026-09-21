"""Prompt templates shared by AI features.

Templates are kept as ``string.Template`` instances so callers cannot
accidentally trigger ``str.format`` on user-supplied text and so that missing
placeholders raise immediately instead of silently producing wrong prompts.
"""

from __future__ import annotations

from string import Template
from typing import Mapping

DIACRITIC_RESTORE_TEMPLATE = Template(
    "Bạn là chuyên gia chuẩn hóa tiếng Việt. Hãy phục hồi dấu dựa trên toàn bộ "
    "ngữ cảnh của câu, không chỉ dựa vào từng từ riêng lẻ.\n"
    "\n"
    "Quy tắc bắt buộc:\n"
    "- Chỉ thêm hoặc sửa dấu theo ngữ cảnh để làm nghĩa rõ ràng và chính xác hơn.\n"
    "- Giữ nguyên từ nước ngoài, tên riêng, tên sản phẩm, mã kỹ thuật, URL, email, "
    "số và ký hiệu.\n"
    "- Nếu một từ không dấu đã phù hợp trong ngữ cảnh, giữ nguyên từ đó.\n"
    "- Tự viết hoa chữ cái đầu câu và sau dấu . ? ! … khi phù hợp.\n"
    "- Giữ nguyên khoảng trắng, xuống dòng và dấu câu nhiều nhất có thể.\n"
    "\n"
    "Một số ví dụ:\n"
    "$few_shot_examples\n"
    "\n"
    "Câu cần khôi phục:\n"
    '"$input_text"\n'
    "\n"
    "Chỉ trả về JSON đúng schema:\n"
    "{\n"
    '  "restored": "<câu sau khi chuẩn hóa>",\n'
    '  "confidence": <0..1>,\n'
    '  "notes": "<ngắn gọn>"\n'
    "}\n"
)


PHRASE_DISAMBIGUATE_TEMPLATE = Template(
    "Bạn là chuyên gia chuẩn hóa tiếng Việt. Hãy chọn phương án đúng cho cụm "
    "viết tắt dựa trên nghĩa của cả câu.\n"
    "\n"
    "Ngữ cảnh:\n"
    '"$context"\n'
    "\n"
    'Cụm từ: "$phrase"\n'
    "Phương án:\n"
    "$options\n"
    "\n"
    "Chỉ trả về JSON đúng schema:\n"
    "{\n"
    '  "choice": "<phương án>",\n'
    '  "confidence": <0..1>,\n'
    '  "reason": "<ngắn gọn>"\n'
    "}\n"
)


UNIFIED_CONTEXT_TEMPLATE = Template(
    "Bạn là AI chuẩn hóa tiếng Việt. Hãy đọc toàn bộ câu rồi tự quyết định:\n"
    "1. Phục hồi hoặc sửa dấu tiếng Việt theo ngữ cảnh.\n"
    "2. Chọn nghĩa đúng cho các từ/cụm viết tắt nhiều nghĩa.\n"
    "3. Chuẩn hóa cụm viết tắt theo nghĩa của cả câu.\n"
    "4. Viết hoa chữ cái đầu câu và sau dấu . ? ! … khi phù hợp.\n"
    "\n"
    "Quy tắc:\n"
    "- Không bắt người dùng chọn nghĩa; hãy tự chọn phương án phù hợp nhất.\n"
    "- Ưu tiên các phương án trong danh sách. NHƯNG nếu không có phương án nào "
    "phù hợp với ngữ cảnh, bạn được phép đề xuất một nghĩa MỚI chưa có trong "
    "danh sách — miễn là nghĩa đó là tiếng Việt thông dụng và khớp với ngữ cảnh "
    "(ví dụ: \"chs\" trong ngữ cảnh rủ đi chơi → \"chơi\"). Khi đưa ra nghĩa mới, "
    "đặt \"is_new\": true và viết \"reason\" ngắn gọn tại sao danh sách hiện tại "
    "không hợp.\n"
    "- Nếu từ không dấu đã phù hợp, ví dụ tên hãng, acronym, mã kỹ thuật hoặc từ "
    "nước ngoài, hãy giữ nguyên.\n"
    "- Không đổi nội dung ngoài phạm vi chuẩn hóa dấu, viết tắt và viết hoa.\n"
    "- Nếu không chắc, giữ phương án hiện tại và giảm confidence.\n"
    "\n"
    "Ngữ cảnh đầy đủ:\n"
    '"$full_text"\n'
    "\n"
    "Các từ/cụm viết tắt cần phân định nghĩa (có thể đề xuất nghĩa ngoài danh sách):\n"
    "$ambiguities\n"
    "\n"
    "Chỉ trả về JSON đúng schema:\n"
    "{\n"
    '  "refined_text": "<câu đã chuẩn hóa>",\n'
    '  "disambiguations": [\n'
    '    {"abbr": "<từ viết tắt>", "chosen": "<nghĩa đúng>", "is_new": <true|false>, "reason": "<ngắn gọn>"}\n'
    "  ],\n"
    '  "confidence": <0..1>\n'
    "}\n"
)


SEMANTIC_VERIFY_TEMPLATE = Template(
    "Bạn là AI chuẩn hóa tiếng Việt. Hãy kiểm tra output hiện tại bằng cách đọc "
    "toàn bộ ngữ cảnh câu.\n"
    "\n"
    "Nhiệm vụ:\n"
    "- Phục hồi/sửa dấu tiếng Việt dựa theo ngữ cảnh.\n"
    "- Giữ nguyên những từ không dấu đã đúng trong ngữ cảnh như tên riêng, acronym, "
    "mã kỹ thuật, từ nước ngoài, URL, email và số.\n"
    "- Tự chọn nghĩa đúng cho từ/cụm viết tắt nhiều nghĩa; không để người dùng chọn.\n"
    "- Chuẩn hóa cụm viết tắt theo nghĩa của cả câu.\n"
    "- Khi danh sách nghĩa hiện có cho một viết tắt không khớp ngữ cảnh, bạn được "
    "phép thay bằng nghĩa MỚI phù hợp hơn (vd. \"chs\" trong ngữ cảnh rủ đi chơi → "
    "\"chơi\"); ghi cặp [cũ, mới] vào \"corrections\".\n"
    "- Tự viết hoa chữ cái đầu câu và sau dấu . ? ! … khi phù hợp.\n"
    "\n"
    "Quy tắc quan trọng:\n"
    "- Với teencode/viết tắt chưa rõ, chủ động suy luận từ cả câu, ngữ cảnh tham chiếu "
    "và cách dùng phổ biến; chọn cách hiểu hợp lý nhất và chuẩn hóa luôn, kể cả khi "
    "confidence thấp. Không yêu cầu người đọc giải nghĩa hoặc chọn phương án.\n"
    "- Không thêm thông tin mới ngoài phạm vi chuẩn hóa.\n"
    "- Nếu phương án hiện tại đã đúng, giữ nguyên và trả confidence cao.\n"
    "- Thiếu nghĩa trong dataset không phải lý do giữ nguyên teencode. Nếu thiếu ngữ cảnh, "
    "ưu tiên nghĩa thông dụng phù hợp nhất; trả confidence trung thực. Chỉ giữ nguyên "
    "khi không tìm được cách giải nghĩa hợp lý, không bịa thêm sự kiện.\n"
    "\n"
    "Output hiện tại cần kiểm tra:\n"
    '"$input_text"\n'
    "\n"
    "Các vị trí có thể nhập nhằng:\n"
    "$ambiguous_positions\n"
    "\n"
    "Chỉ trả về JSON đúng schema:\n"
    "{\n"
    '  "verified_text": "<câu đã kiểm tra/sửa>",\n'
    '  "corrections": [["từ hoặc cụm cũ", "từ hoặc cụm mới"], ...],\n'
    '  "confidence": <0..1>\n'
    "}\n"
)


def render(template: Template, placeholders: Mapping[str, str]) -> str:
    """Render ``template`` substituting every key in ``placeholders``.

    Raises ``KeyError`` if the template references a placeholder we did not
    supply. That is by design: a missing field is a programmer error, not
    something we want to ship as silent empty text to a paid model.
    """
    return template.substitute(placeholders)
