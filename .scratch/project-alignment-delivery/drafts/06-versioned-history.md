# 06: Gắn kết quả và lịch sử với đúng phiên bản đầu vào

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Priority: P0
Type: implementation

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): H-01–03, R-11; AC-06, AC-18.

## Vấn đề cần giải quyết

latestText và latestData có thể thuộc hai request; response cũ hoặc rời trang làm ghép sai lịch sử.

## Vì sao quan trọng

Lịch sử và kết quả phải đại diện chính xác nội dung người dùng đã chuẩn hóa.

## Kết quả mong muốn / What to build

Mỗi kết quả hiển thị/copy/lưu nhận diện được đúng phiên bản input; lịch sử giữ trạng thái một phần nếu có.

## Ràng buộc

Không đổi chính sách retention; không xóa dữ liệu cũ. Chỉ mở rộng metadata cần để gắn phiên và trạng thái.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [ ] Response cũ không ghi đè sau khi input đổi, kể cả trong khoảng debounce.
- [ ] Rời trang hoặc xóa input khi request chưa xong không lưu input mới với output cũ.
- [ ] Lưu một phần có trạng thái đúng từ contract AI; không tạo bản ghi cho từng phím gõ.
- [ ] Kiểm thử kiểm soát thứ tự response và flush-history; lịch sử của mình vẫn xem/xóa được.

## Blocked by

- [05 — Hiển thị đúng phạm vi và lý do chưa được AI kiểm tra](05-truthful-ai-status.md)

## Khu vực có thể ảnh hưởng

useLiveNormalize; WorkspacePage/history snapshot; history API/repository/schema; UI race tests.

## Comments

### Chính sách dùng chung đã chốt — 2026-09-07

Kết quả lưu cần truy vết phiên bản nghĩa/chính sách đã dùng để xác định tác động khi thu hồi, không viết lại lịch sử cũ. Xem [chính sách và nghiệm thu](../shared-meaning-policy.md). Đây là yêu cầu mới cần kiểm chứng, không tự đóng ticket.

### Cập nhật mục tiêu — 2026-09-07 (sau tích hợp Nemotron)

Review output suy đoán và metadata đi cùng đúng phiên bản khi copy/lưu/đọc lịch sử, kể cả response muộn và cache. Chưa có bằng chứng mới nghiệm thu end-to-end lịch sử.

Áp dụng [hồ sơ thay đổi và checklist review tổng thể](../teencode-policy-change.md). Ghi chú trái chính sách mới bên dưới là lịch sử; không tự đánh dấu các tiêu chí chưa kiểm chứng.


Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.

