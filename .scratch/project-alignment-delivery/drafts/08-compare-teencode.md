# 08: Đối chiếu hai ô tương đương với highlight teencode hai phía

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Priority: P1
Type: implementation

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): R-01–05, R-11; AC-12–13.

## Vấn đề cần giải quyết

Hai ô trình bày khác nhau; span hiện chỉ hướng output và có thể nhầm từ lặp.

## Vì sao quan trọng

Người dùng cần nhìn được đúng phần nào của bản gốc đã trở thành phần nào ở kết quả.

## Kết quả mong muốn / What to build

Một đường hoàn chỉnh từ mở rộng teencode đến highlight gốc/kết quả, hai ô tương đương và copy plain text.

## Ràng buộc

Slice đầu tiên chỉ hoàn thiện teencode; mở rộng schema nhỏ đủ dùng chung cho các slice sau, không thay editor thư viện nếu chưa cần.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [ ] Chọn thay đổi teencode xác định đúng vị trí gốc/kết quả, kể cả từ lặp và expansion dài hơn.
- [ ] Hai ô có font/wrap/không gian sử dụng tương đương trên rộng/hẹp; input gốc không bị ghi đè.
- [ ] Màu kèm nhãn/mô tả, không chỉ dựa vào màu; copy không có markup.
- [ ] Có test workspace qua backend/fake AI cho remap sau thay đổi; không tạo framework provenance cho mọi tính năng chưa dùng.

## Blocked by

- [03 — Giữ khoảng cách và ranh giới đoạn qua toàn bộ chuẩn hóa](03-preserve-format.md)
- [04 — Bảo vệ URL, mã, số và ngoại ngữ đã nhận diện](04-protect-literals.md)

## Khu vực có thể ảnh hưởng

Live change metadata; response/types; LiveInputEditor; HighlightedOutput/NormalizedOutputPane; styles.

## Comments

### Cập nhật mục tiêu — 2026-09-07 (sau tích hợp Nemotron)

Review highlight hai phía cho nghĩa AI ngoài dataset và confidence thấp, từ lặp và offset sau thay thế. Không mặc định chỉ expansion từ dataset mới là thay đổi cần đối chiếu.

Áp dụng [hồ sơ thay đổi và checklist review tổng thể](../teencode-policy-change.md). Ghi chú trái chính sách mới bên dưới là lịch sử; không tự đánh dấu các tiêu chí chưa kiểm chứng.


Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.

