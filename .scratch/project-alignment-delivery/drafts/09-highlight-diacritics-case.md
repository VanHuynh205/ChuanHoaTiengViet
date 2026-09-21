# 09: Giải thích sửa dấu và viết hoa bằng highlight

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Priority: P1
Type: implementation

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): R-02–05; AC-12.

## Vấn đề cần giải quyết

Sửa dấu và viết hoa không được biểu diễn đầy đủ như thay đổi có vị trí.

## Vì sao quan trọng

Người dùng không thể kiểm tra loại sửa phổ biến nhất.

## Kết quả mong muốn / What to build

Highlight sửa dấu/chính tả đã có và viết hoa trên hai phía, bao gồm một thay đổi nhiều loại.

## Ràng buộc

Chưa bổ sung thuật toán sửa chính tả mới; chỉ giải thích các sửa đã thực hiện.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [ ] Chỉ sửa dấu vẫn tạo highlight có nhãn đúng; không bị loại như test cũ.
- [ ] Viết hoa có vị trí và nhãn riêng, không nhầm thành mở rộng teencode.
- [ ] Thay đổi teencode kèm dấu/viết hoa có một màu chính và xem đủ các loại.
- [ ] Từ lặp và Unicode tiếng Việt giữ offset hợp lệ; plain copy không thay đổi.

## Blocked by

- [08 — Đối chiếu hai ô tương đương với highlight teencode hai phía](08-compare-teencode.md)

## Khu vực có thể ảnh hưởng

Diacritic/capitalization change emission; change response; highlight details; UI integration tests.

## Comments

Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.

