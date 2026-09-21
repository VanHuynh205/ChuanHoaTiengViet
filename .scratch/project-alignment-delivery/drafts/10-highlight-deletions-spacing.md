# 10: Hiển thị phần emoji bị xóa và thay đổi khoảng trắng

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Priority: P1
Type: implementation

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): R-02–05, N-04; AC-07, AC-12.

## Vấn đề cần giải quyết

Nội dung bị xóa không có vị trí ở output nên một kiểu highlight từ thay thế không thể giải thích.

## Vì sao quan trọng

User cần thấy cả phần biến mất và biết cấu trúc văn bản có bị đổi không.

## Kết quả mong muốn / What to build

Đối chiếu được emoji/emoticon bị xóa và các thay đổi whitespace thực sự phát sinh.

## Ràng buộc

Không xóa thêm ký tự ngoài phạm vi đã chốt; không khôi phục emoji vào output.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [ ] Emoji/emoticon bị xóa có dấu hiệu ở bản gốc và điểm đối chiếu kết quả.
- [ ] Whitespace thay đổi thật được biểu diễn rõ; không tạo sửa mới để có highlight.
- [ ] Nhiều emoji hoặc xóa sát nhau không làm lệch vị trí thay đổi sau đó.
- [ ] Mô tả không dựa vào màu và copy vẫn thuần văn bản; giữ đoạn theo ticket bảo toàn định dạng.

## Blocked by

- [08 — Đối chiếu hai ô tương đương với highlight teencode hai phía](08-compare-teencode.md)

## Khu vực có thể ảnh hưởng

Emoji removal/change map; whitespace handling; source/output highlight; integration tests.

## Comments

Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.

