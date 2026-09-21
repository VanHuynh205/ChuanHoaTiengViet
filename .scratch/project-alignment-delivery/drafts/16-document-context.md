# 16: Xử lý văn bản dài theo ngữ cảnh xuyên đoạn

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Implementation: complete — theo yêu cầu thực hiện mới, fake AI
Evidence: ../execution-evidence.md
Priority: P1
Type: implementation

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): Luồng dán; N-01, R-07–09; AC-02, AC-05, AC-07.

## Vấn đề cần giải quyết

Chunk độc lập và trần số chunk làm thiếu ngữ cảnh/toàn văn mà không biểu diễn đầy đủ.

## Vì sao quan trọng

Đoạn giải thích trước có thể quyết định nghĩa ở đoạn sau; 5.000 từ là phạm vi mục tiêu.

## Kết quả mong muốn / What to build

Dán văn bản dài tự xử lý từng phần với ngữ cảnh liên quan, giữ đoạn và minh bạch phần chưa kiểm tra.

## Ràng buộc

Không mặc định gửi toàn bộ 5.000 từ mỗi call hoặc tăng context window để thay chính sách budget.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [x] Ví dụ viết tắt được giải thích ở đoạn trước được xét đúng khi đoạn sau qua ranh giới chunk.
- [x] Bộ văn bản khoảng 5.000 từ không bị cắt âm thầm; nếu budget không đủ thì giữ phần chưa xử lý và trạng thái phạm vi rõ.
- [x] Có tiến độ, copy một phần và không mất xuống dòng; sửa ngữ cảnh liên quan không yêu cầu rewrite vô hạn toàn văn.
- [x] Test dùng provider xác định và tài liệu nhiều đoạn; số đo Kimi thật thuộc điều tra nghiệm thu, không được bịa đạt SLA.

## Blocked by

- [03 — Giữ khoảng cách và ranh giới đoạn qua toàn bộ chuẩn hóa](03-preserve-format.md)
- [15 — Trả kết quả dataset sớm và cập nhật AI sau khoảng nghỉ gõ](15-progressive-typing.md)

## Khu vực có thể ảnh hưởng

Document segmentation/context selection; live delivery; AI scope metadata; workspace progress.

## Comments

### Cập nhật mục tiêu — 2026-09-07 (sau tích hợp Nemotron)

Review tài liệu trộn chunk chắc chắn, suy đoán và bị bỏ qua/lỗi; không mất output đã giải nghĩa hay nhãn suy đoán khi tổng hợp confidence và scope. Test cơ chế cũ không tự nghiệm thu tổ hợp mới.

Áp dụng [hồ sơ thay đổi và checklist review tổng thể](../teencode-policy-change.md). Ghi chú trái chính sách mới bên dưới là lịch sử; không tự đánh dấu các tiêu chí chưa kiểm chứng.


Chunk giữ ranh giới đoạn/literal, kèm context gốc có giới hạn và đưa context vào cache key. Có NDJSON snapshot từng phần, copy và trạng thái phạm vi; test 5.000 từ hết quota không mất từ hoặc xuống dòng. Chưa đo Kimi hoặc SLA thật. Các dòng “chưa triển khai” còn lại là lịch sử draft.

Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.
