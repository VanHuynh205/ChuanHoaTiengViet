# 15: Trả kết quả dataset sớm và cập nhật AI sau khoảng nghỉ gõ

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Implementation: complete — theo yêu cầu thực hiện mới, fake AI
Evidence: ../execution-evidence.md
Priority: P1
Type: implementation

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): Luồng nhập tay; R-07, R-11–12; AC-03, AC-06, AC-13.

## Vấn đề cần giải quyết

Workspace chờ response đầy đủ; gõ nghỉ chưa kết câu có thể không được AI xét.

## Vì sao quan trọng

Realtime cần kết quả ban đầu nhanh nhưng không gọi lại toàn văn cho mọi phím.

## Kết quả mong muốn / What to build

User thấy phần dataset trước, AI cập nhật đúng phiên sau khoảng nghỉ hoặc ranh giới câu; copy được trạng thái đang có.

## Ràng buộc

Không chốt mili-giây SLA tùy ý; không yêu cầu streaming token; long-document context nằm ở slice sau.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [x] Fake provider chậm không chặn xuất hiện kết quả dataset của input hiện tại.
- [x] Khoảng nghỉ gõ đủ điều kiện tạo xét AI dù không có dấu kết câu; gõ tiếp không làm response cũ ghi đè.
- [x] Không xử lý lại phần không liên quan hoặc call trùng không cần thiết; budget vẫn áp dụng.
- [x] Tiến độ/kết quả copy/lịch sử có trạng thái phiên đúng; không cần đổi transport cụ thể nếu giải pháp hiện có đáp ứng.

## Blocked by

- [06 — Gắn kết quả và lịch sử với đúng phiên bản đầu vào](06-versioned-history.md)
- [14 — Tự gọi AI cho phần khó sau dataset, kể cả câu ngắn](14-automatic-ai-routing.md)

## Khu vực có thể ảnh hưởng

Workspace/live hook; request lifecycle; backend normalization delivery; history version metadata.

## Comments

### Cập nhật mục tiêu — 2026-09-07 (sau tích hợp Nemotron)

Review snapshot AI suy đoán sau dataset, cache-hit, debounce và response cũ; output cùng nhãn phải thuộc đúng phiên bản. Giữ nguyên quy tắc consent/ngân sách.

Áp dụng [hồ sơ thay đổi và checklist review tổng thể](../teencode-policy-change.md). Ghi chú trái chính sách mới bên dưới là lịch sử; không tự đánh dấu các tiêu chí chưa kiểm chứng.


Dataset trả trước; AI đợi idle 700 ms hoặc ranh giới câu, không coi debounce là SLA. Abort/version key chặn output cũ; copy dùng snapshot đang có. Lịch sử kiểm tra input khớp và dùng web_live_partial cho phần chưa hoàn tất. Có test AI chậm, response muộn, stream gián đoạn và Playwright lưu giữa chừng. Các dòng “chưa triển khai” còn lại là lịch sử draft.

Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.
