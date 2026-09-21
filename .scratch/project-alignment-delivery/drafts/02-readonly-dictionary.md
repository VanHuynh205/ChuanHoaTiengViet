# 02: Đưa user về quyền chỉ xem từ điển và bỏ form hỏi nghĩa

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Priority: P0
Type: implementation

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): D-01, D-07; AC-16.

## Vấn đề cần giải quyết

Workspace và dictionary cho user thêm nghĩa riêng, pending yêu cầu user giải nghĩa.

## Vì sao quan trọng

Người dán văn bản có thể không biết nghĩa; chỉ admin được quản lý nghĩa.

## Kết quả mong muốn / What to build

User xem/tìm từ điển và sử dụng chuẩn hóa mà không có form tạo nghĩa riêng hoặc câu hỏi nghĩa gốc.

## Ràng buộc

Không xóa bảng/dữ liệu cũ hoặc endpoint bằng thao tác phá hủy. Loại ảnh hưởng nghĩa riêng vào kết quả nằm ở ticket giữ nguyên bất định.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [ ] User gọi trực tiếp API ghi nghĩa riêng bị từ chối; UI không cung cấp đường nhập nghĩa.
- [ ] Pending chưa rõ không yêu cầu user giải thích để tiếp tục chuẩn hóa.
- [ ] Admin vẫn thêm/sửa/duyệt nghĩa qua các chức năng admin phù hợp hiện có.
- [ ] Dữ liệu nghĩa riêng cũ không bị xóa trong ticket này; kiểm tra regression phần từ điển chỉ đọc.

## Blocked by

None (can start immediately sau khi ticket được duyệt).

## Khu vực có thể ảnh hưởng

WorkspacePage; PendingNotice/HighlightedOutput; AdminDictionaryPage; user-meaning API; kiểm thử quyền.

## Comments

Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.

