# 01: Chặn truy cập lịch sử riêng của người khác

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Priority: P0
Type: implementation

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): H-04, H-06; AC-17.

## Vấn đề cần giải quyết

Admin hiện có UI/API đọc và xóa lịch sử của user khác.

## Vì sao quan trọng

Quyền quản lý tài khoản không được đồng nghĩa với quyền đọc nội dung riêng.

## Kết quả mong muốn / What to build

Mỗi tài khoản chỉ xem/xóa lịch sử của chính mình; admin tiếp tục quản lý tài khoản theo quyền sẵn có.

## Ràng buộc

Không xóa lịch sử đã lưu; không mở rộng quản lý tài khoản; giữ auth/session đã ALIGNED.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [ ] User và admin bị từ chối khi gọi trực tiếp đường đọc/xóa lịch sử thuộc tài khoản khác.
- [ ] UI quản lý tài khoản không còn hiển thị hoặc thao tác lịch sử người khác.
- [ ] Xem/xóa lịch sử của mình vẫn hoạt động, kể cả tài khoản admin.
- [ ] Kiểm thử UI và API xác thực với hai chủ sở hữu chứng minh không chỉ ẩn nút.

## Blocked by

None (can start immediately sau khi ticket được duyệt).

## Khu vực có thể ảnh hưởng

History API/repository; AdminAccountsPage; history/account API wrappers; kiểm thử phân quyền.

## Comments

Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.

