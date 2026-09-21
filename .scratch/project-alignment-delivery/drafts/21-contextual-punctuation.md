# 21: Bổ sung dấu câu có căn cứ và highlight phần được thêm

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Priority: P1
Type: implementation
Implementation: hoàn tất module policy bảo thủ + test + provenance insertions/UI theo yêu cầu 2026-09-09

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): N-06–07, R-02–05; AC-11–12.

## Vấn đề cần giải quyết

Chưa có đường khôi phục dấu câu với chính sách bất định và giải thích vị trí thêm.

## Vì sao quan trọng

Dấu ?/! có thể làm đổi ý định hoặc cảm xúc của người viết.

## Kết quả mong muốn / What to build

Dấu câu chỉ được thêm khi có cơ sở ngữ cảnh; UI giải thích phần thêm mà không đổi văn phong.

## Ràng buộc

Không thêm dấu chỉ để câu trông hoàn chỉnh; không cam kết thuật toán hoặc ngưỡng chưa được đo.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [ ] Câu đủ căn cứ được thêm dấu thích hợp; câu thiếu căn cứ không bị ép thành câu hỏi/cảm thán.
- [ ] Viết hoa đi kèm không tác động URL/tên/mã hoặc đầu chunk/wrap.
- [ ] Phần thêm có điểm đối chiếu bản gốc và màu/nhãn dấu câu; copy không kèm markup.
- [ ] Ví dụ kiểm thử bao phủ câu hỏi rõ, câu mơ hồ, dấu có sẵn và số/URL chứa dấu chấm.

## Blocked by

- [04 — Bảo vệ URL, mã, số và ngoại ngữ đã nhận diện](04-protect-literals.md)
- [08 — Đối chiếu hai ô tương đương với highlight teencode hai phía](08-compare-teencode.md)
- [14 — Tự gọi AI cho phần khó sau dataset, kể cả câu ngắn](14-automatic-ai-routing.md)

## Khu vực có thể ảnh hưởng

Punctuation policy/AI result; capitalization; change provenance; source/output highlight.

## Comments

### Hoàn tất phạm vi được giao — 2026-09-09

Policy riêng chỉ nhận mẫu hỏi đầu câu rõ ràng, giữ literals/dấu có sẵn, thêm một `?`, không `!`; AI không được tự thay dấu ngoài policy. Metadata source span rỗng/output span trỏ dấu mới, input marker và output highlight, copy plain text có test. Xem [biên bản nghiệm thu](../../../docs/tickets-17-20-21-verification.md). Ghi chú “chưa triển khai” bên dưới là lịch sử.

### Cập nhật mục tiêu — 2026-09-07 (sau tích hợp Nemotron)

Ngoại lệ teencode không cho phép tự thêm dấu hỏi/cảm thán thiếu căn cứ. Review câu trộn teencode/dấu câu và bảo toàn giọng điệu.

Áp dụng [hồ sơ thay đổi và checklist review tổng thể](../teencode-policy-change.md). Ghi chú trái chính sách mới bên dưới là lịch sử; không tự đánh dấu các tiêu chí chưa kiểm chứng.


Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.

