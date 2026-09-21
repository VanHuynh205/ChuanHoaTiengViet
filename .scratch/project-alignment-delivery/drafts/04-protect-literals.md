# 04: Bảo vệ URL, mã, số và ngoại ngữ đã nhận diện

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Priority: P0
Type: implementation

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): N-05, N-06, N-08; AC-08, AC-11.

## Vấn đề cần giải quyết

Viết hoa theo dấu chấm sửa cả domain URL; ghép token tách tỷ lệ số; chưa có bảo vệ xuyên các bước.

## Vì sao quan trọng

Kết quả có thể phá nội dung dùng được và làm đổi dữ liệu ngoài tiếng Việt.

## Kết quả mong muốn / What to build

Các vùng đã nhận diện cần giữ nguyên không bị viết hoa, thêm dấu hoặc tách khoảng trắng bên trong.

## Ràng buộc

Không xây bộ nhận diện ngôn ngữ tổng quát, không đổi case mọi tên riêng; giữ đúng vùng chắc chắn và ghi rõ giới hạn.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [ ] URL/email, C++/C#, 9/10, 50% và tên sản phẩm trong bộ ví dụ giữ nguyên nội dung.
- [ ] Đầu câu tiếng Việt vẫn viết hoa; không viết hoa giữa URL hoặc do ranh giới chunk/wrap.
- [ ] Ngoại ngữ có bằng chứng nhận diện không bị sửa chỉ vì trùng từ không dấu; trường hợp chưa đủ căn cứ không ép Việt hóa.
- [ ] Chứng minh bảo vệ qua pipeline/live response và text copy; không tuyên bố nhận diện mọi ngôn ngữ hoàn hảo.

## Blocked by

None (can start immediately sau khi ticket được duyệt).

## Khu vực có thể ảnh hưởng

Tokenization/capitalization; diacritic/live normalization; vùng bảo vệ; regression mixed-language.

## Comments

Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.

