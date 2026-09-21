# 20: Sửa lỗi chính tả có căn cứ và giải thích thay đổi

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Priority: P1
Type: implementation
Implementation: hoàn tất phạm vi seed + fixture regression + provenance/UI theo yêu cầu 2026-09-09

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): N-02–03, N-08, R-02; AC-08–09, AC-12.

## Vấn đề cần giải quyết

Khôi phục dấu không bao phủ lỗi chính tả tổng quát; không được coi sửa tình cờ bởi AI là capability.

## Vì sao quan trọng

Văn bản đánh giá cần sửa lỗi rõ ràng nhưng không biến ngoại ngữ hoặc phủ định thành từ khác.

## Kết quả mong muốn / What to build

Các lỗi chính tả trong bộ ví dụ có căn cứ được sửa và highlight; trường hợp chưa chắc giữ nguyên.

## Ràng buộc

Không xây từ điển mới hoặc model riêng, không biến mọi từ OOV thành lỗi; tiêu chí định lượng còn theo wayfinding.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [ ] Bộ ví dụ kiểm chứng có lỗi gõ tiếng Việt, từ đúng hiếm gặp, ngoại ngữ và phủ định.
- [ ] Thay đổi đúng có provenance/nhãn dấu-chính tả hai phía; không sửa ngoài bằng chứng.
- [ ] AI lỗi hoặc chưa chắc không làm mất nguyên bản phần liên quan.
- [ ] Test qua workspace/backend với fake AI kiểm cơ chế; không tuyên bố chất lượng toàn bộ Kimi từ test giả lập.

## Blocked by

- [04 — Bảo vệ URL, mã, số và ngoại ngữ đã nhận diện](04-protect-literals.md)
- [07 — Giữ nguyên bất định và bỏ yêu cầu chọn biến thể](07-safe-uncertainty.md)
- [09 — Giải thích sửa dấu và viết hoa bằng highlight](09-highlight-diacritics-case.md)
- [14 — Tự gọi AI cho phần khó sau dataset, kể cả câu ngắn](14-automatic-ai-routing.md)

## Khu vực có thể ảnh hưởng

Spelling policy in normalization/AI; protected regions; change metadata; comparison UI.

## Comments

### Hoàn tất phạm vi được giao — 2026-09-09

Giữ seed; thêm 14 fixture có nhãn positive/negative/mixed, kiểm thử luồng live và phân biệt spelling/teencode. Metadata `known_typo`/0.99 phát sinh từ quy tắc, UI highlight/tooltip theo metadata. Xem [biên bản nghiệm thu](../../../docs/tickets-17-20-21-verification.md). Kết quả chỉ đo capability seed hiện tại, không tuyên bố chất lượng model hoặc chính tả tổng quát. Ghi chú “chưa triển khai” bên dưới là lịch sử.

### Cập nhật mục tiêu — 2026-09-07 (sau tích hợp Nemotron)

Ngoại lệ áp dụng confidence thấp dành cho giải nghĩa teencode, không mở rộng mặc nhiên sang mọi sửa chính tả. Review câu trộn teencode và chính tả để phát hiện sửa ngoài phạm vi.

Áp dụng [hồ sơ thay đổi và checklist review tổng thể](../teencode-policy-change.md). Ghi chú trái chính sách mới bên dưới là lịch sử; không tự đánh dấu các tiêu chí chưa kiểm chứng.


Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.

