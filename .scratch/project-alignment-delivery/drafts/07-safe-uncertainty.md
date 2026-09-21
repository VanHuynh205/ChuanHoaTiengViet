# 07: Chủ động giải nghĩa teencode và thể hiện bất định

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Priority: P0
Type: implementation

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): N-01, N-10–12, D-06–07, R-06; AC-01.

## Vấn đề cần giải quyết

Dataset lấy nghĩa đầu tiên khi thiếu căn cứ; fallback giữ phỏng đoán; UI vẫn chọn biến thể.

## Vì sao quan trọng

Tự động toàn bộ phải tránh làm đổi nghĩa khi không thể xác định.

## Kết quả mong muốn / What to build

AI chủ động chọn nghĩa hợp lý nhất cho teencode và áp dụng cả đề xuất chưa chắc chắn với nhãn suy đoán; không có đề xuất hợp lệ thì giữ nguyên. User không cần chọn nghĩa.

## Ràng buộc

Không giải quyết mọi bài toán hiểu ngữ cảnh, không xóa hàng loạt dữ liệu user overrides; chỉ bỏ ảnh hưởng và workflow trái spec.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [x] Teencode có đề xuất AI hợp lệ dưới ngưỡng confidence được áp dụng trong verifier/cache và live service; trạng thái vẫn thể hiện bất định (test fake đã đạt).
- [ ] Review tổng thể: suy đoán theo ngữ cảnh không bị biến thành lựa chọn dataset mặc định hoặc thông báo chắc chắn; kiểm chứng highlight/copy/lịch sử.

- [ ] Một viết tắt nhiều nghĩa không có bằng chứng giữ nguyên khi AI không chạy/lỗi.
- [ ] Nghĩa đã duyệt nhưng không phù hợp ngữ cảnh không được cưỡng ép chọn theo thứ tự danh sách.
- [ ] UI có dấu hiệu bất định riêng và không yêu cầu chọn biến thể để tiếp tục.
- [ ] Nghĩa riêng user đã lưu trước đây không tiếp tục chi phối kết quả; không xóa dữ liệu cũ.
- [ ] Dùng fake AI chứng minh fallback không giữ một suy đoán đã bị xác định là thiếu căn cứ.

## Blocked by

- [02 — Đưa user về quyền chỉ xem từ điển và bỏ form hỏi nghĩa](02-readonly-dictionary.md)

## Khu vực có thể ảnh hưởng

Contextual abbreviation/live normalizer; response ambiguity; variant/ambiguity UI; live-data override merge.

## Comments

### Cập nhật mục tiêu — 2026-09-07 (sau tích hợp Nemotron)

Yêu cầu giữ nguyên khi thiếu căn cứ được thay cho teencode có đề xuất AI hợp lệ: áp dụng nghĩa hợp lý nhất, ghi rõ suy đoán. Khi AI không chạy/lỗi hoặc không giải nghĩa được, vẫn giữ nguyên. Chỉ phần thay đổi này đã có test; không tự đóng toàn ticket.

Áp dụng [hồ sơ thay đổi và checklist review tổng thể](../teencode-policy-change.md). Ghi chú trái chính sách mới bên dưới là lịch sử; không tự đánh dấu các tiêu chí chưa kiểm chứng.


Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.

