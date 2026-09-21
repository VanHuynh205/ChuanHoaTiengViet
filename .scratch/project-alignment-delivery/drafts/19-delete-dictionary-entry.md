# 19: Cho admin xóa mục viết tắt khỏi từ điển hiệu lực

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Priority: P1
Type: implementation

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): D-02, D-08; AC-15–16.

## Vấn đề cần giải quyết

Có thêm/sửa nhưng chưa có luồng xóa mục viết tắt chung hoàn chỉnh.

## Vì sao quan trọng

Admin cần loại mục sai mà nó không xuất hiện lại từ cache/JSON.

## Kết quả mong muốn / What to build

Admin xóa/ngừng hiệu lực một mục, user không còn thấy hoặc bị áp dụng mục đó ở lần chuẩn hóa tiếp theo.

## Ràng buộc

Chọn ngừng hiệu lực hay xóa vật lý trong phạm vi dữ liệu đã xác minh; không purge dữ liệu hàng loạt.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [ ] Admin thực hiện xóa qua UI/API; user trực tiếp gọi thao tác bị từ chối.
- [ ] Mục không quay lại qua JSON/bootstrap/cache sau thao tác theo contract nhất quán đã hoàn tất.
- [ ] Có kết quả thành công/lỗi rõ và giữ trace quyết định cần thiết.
- [ ] Test bao phủ mục có nhiều nghĩa; phạm vi là xóa mục, không tự thêm chức năng quản lý từng nghĩa chưa chốt.

## Blocked by

- [18 — Áp dụng cập nhật từ điển nhất quán sau khi admin lưu](18-dictionary-consistency.md)

## Khu vực có thể ảnh hưởng

AdminDictionaryPage; dictionary API/repository; effective dataset and sync; audit tests.

## Comments

### Chính sách dùng chung đã chốt — 2026-09-07

Admin có thể thu hồi nghĩa tự cho dùng theo ngữ cảnh; phải có audit, ngừng tái sử dụng và chống hồi sinh. Không âm thầm thay lịch sử đã lưu. Xem [chính sách và nghiệm thu](../shared-meaning-policy.md). Đây là yêu cầu mới cần kiểm chứng, không tự đóng ticket.

Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.

