# 11: Cho phép dataset-only và thông báo trước khi gửi AI

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Priority: P0
Type: implementation

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): A-07–10, R-08; AC-19.

## Vấn đề cần giải quyết

Workspace tự gửi AI mà chưa có lựa chọn dataset-only/thông báo phù hợp.

## Vì sao quan trọng

User phải kiểm soát việc gửi dữ liệu ngoài, và ứng dụng không được hứa quyền riêng tư sai.

## Kết quả mong muốn / What to build

User chọn không gửi AI vẫn chuẩn hóa bằng dataset; lựa chọn có hiệu lực ở backend, trạng thái nói rõ giới hạn.

## Ràng buộc

Không tự xác nhận trial phù hợp production. Cơ chế consent không thay quyền sử dụng provider. Không bắt buộc dùng bảng preferences cũ.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [ ] Khi chưa cho phép hoặc chọn dataset-only, cả các đường AI liên quan không phát sinh inference.
- [ ] User vẫn nhập/dán/copy và xem trạng thái thiếu AI rõ ràng.
- [ ] Thông báo phản ánh ràng buộc đã có bằng chứng; không hứa zero-retention/no-training hoặc ẩn danh hoàn hảo.
- [ ] Kiểm thử backend qua fake provider xác nhận không có call; lựa chọn không thể bị một luồng phụ bỏ qua.

## Blocked by

- [05 — Hiển thị đúng phạm vi và lý do chưa được AI kiểm tra](05-truthful-ai-status.md)

## Khu vực có thể ảnh hưởng

Workspace controls; normalize request/context; AI service admission; status UI; integration tests.

## Comments

### Chính sách dùng chung đã chốt — 2026-09-07

Cần xác định rõ nghĩa AI dùng có điều kiện có thuộc dataset-only hay không khi triển khai; không tự gửi inference hoặc gắn nhãn dữ liệu đã xác nhận cho ứng viên. Xem [chính sách và nghiệm thu](../shared-meaning-policy.md). Đây là yêu cầu mới cần kiểm chứng, không tự đóng ticket.

### Cập nhật mục tiêu — 2026-09-07 (sau tích hợp Nemotron)

Local AI_DISABLE_NETWORK hiện là 0; lựa chọn cho phép gửi AI và dataset-only vẫn phải được backend thực thi. Bật cấu hình local không thay quyết định phạm vi dữ liệu/trial.

Áp dụng [hồ sơ thay đổi và checklist review tổng thể](../teencode-policy-change.md). Ghi chú trái chính sách mới bên dưới là lịch sử; không tự đánh dấu các tiêu chí chưa kiểm chứng.


Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.

