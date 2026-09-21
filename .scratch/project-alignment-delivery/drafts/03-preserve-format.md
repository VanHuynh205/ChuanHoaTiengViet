# 03: Giữ khoảng cách và ranh giới đoạn qua toàn bộ chuẩn hóa

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Priority: P0
Type: implementation

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): N-04, N-09; AC-07.

## Vấn đề cần giải quyết

Xóa emoticon, khôi phục dấu và ghép segment có đường gộp whitespace hoặc tái tạo khoảng cách sai.

## Vì sao quan trọng

Văn bản dài và bản đối chiếu mất cấu trúc dù từng bước có vẻ đúng.

## Kết quả mong muốn / What to build

Nhập/dán văn bản giữ cấu trúc đoạn và khoảng cách có ý nghĩa sau các bước chuẩn hóa.

## Ràng buộc

Không thêm chuẩn hóa whitespace tùy ý, không đổi thuật toán ngôn ngữ tổng thể; refactor cục bộ chỉ khi cần để giữ separator.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [ ] Văn bản có emoticon và nhiều dòng trống không bị gộp đoạn.
- [ ] Sửa dấu hoặc chia/ghép segment không tự đổi separator gốc giữa đoạn.
- [ ] Ví dụ ngoặc và khoảng cách quanh từ không tạo 'chao( ban)' từ 'chao (ban)'.
- [ ] Có kiểm thử qua đường live cho cả đoạn ngắn và văn bản buộc chia segment; không chỉ test tokenizer.

## Blocked by

None (can start immediately sau khi ticket được duyệt).

## Khu vực có thể ảnh hưởng

Emoji remover; diacritic restorer; text utilities; incremental/live normalizer; live API tests.

## Comments

Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.

