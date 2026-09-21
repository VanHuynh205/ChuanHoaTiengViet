# 14: Tự gọi AI cho phần khó sau dataset, kể cả câu ngắn

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Implementation: complete — theo yêu cầu thực hiện mới, fake AI
Evidence: ../execution-evidence.md
Priority: P1
Type: implementation

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): N-02–03, N-11–13, A-03; AC-01, AC-03, AC-09–10, AC-22.

## Vấn đề cần giải quyết

Gate độ dài/dấu kết thúc bỏ sót từ khó và sửa dataset đáng nghi; các đường AI có policy khác nhau.

## Vì sao quan trọng

Tự động phải dựa vào nhu cầu ngữ cảnh, không bắt người dùng bù cho gate kỹ thuật.

## Kết quả mong muốn / What to build

Luồng chính đánh giá phần chưa rõ/sửa đáng nghi và tự yêu cầu AI khi được phép; áp dụng nghĩa teencode hợp lý nhất kể cả confidence thấp với nhãn suy đoán, giữ fallback khi không có đề xuất hợp lệ.

## Ràng buộc

Chỉ gom chính sách cần cho slice; không hợp nhất toàn bộ pipeline CLI/API hoặc mở rộng AI thành agent/tool-use.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [x] Đề xuất teencode confidence thấp không bị loại chỉ vì ngưỡng; cache và output giữ kết quả cùng trạng thái bất định (bằng chứng ở hồ sơ cập nhật).
- [ ] Đo bao phủ nhận diện teencode ngoài dataset trên bộ ví dụ đại diện; ghi rõ các dạng còn bỏ sót thay vì tuyên bố mọi từ lạ đều được gửi AI.

- [x] Câu ngắn có từ khó và câu có sửa dataset đáng nghi đều được đánh giá AI, không chỉ so ngưỡng ký tự.
- [x] Dataset-only và budget từ chối vẫn có hiệu lực; không phát sinh call ở đường phụ.
- [x] AI thiếu căn cứ/sửa trái vùng bảo vệ không biến thành kết quả chắc chắn; nội dung ra lệnh trong input không đổi chính sách.
- [x] Fake provider chứng minh đường chính hoàn chỉnh và xử lý lỗi; không bắt buộc model thật để nghiệm thu điều phối.

## Blocked by

- [07 — Giữ nguyên bất định và bỏ yêu cầu chọn biến thể](07-safe-uncertainty.md)
- [11 — Cho phép dataset-only và thông báo trước khi gửi AI](11-dataset-only-choice.md)
- [12 — Áp dụng ngân sách AI chung và giới hạn theo user](12-shared-ai-budget.md)

## Khu vực có thể ảnh hưởng

Live routing/service; semantic verifier/disambiguation contract; prompt/result checks; ambiguity UI.

## Comments

### Cập nhật mục tiêu — 2026-09-07 (sau tích hợp Nemotron)

Không chỉ gọi AI mà phải áp dụng đề xuất teencode hợp lệ dưới ngưỡng confidence và báo suy đoán. Bộ nhận diện vẫn có thể bỏ sót teencode ngoài dataset; bao phủ mọi chuỗi lạ chưa được chứng minh.

Áp dụng [hồ sơ thay đổi và checklist review tổng thể](../teencode-policy-change.md). Ghi chú trái chính sách mới bên dưới là lịch sử; không tự đánh dấu các tiêu chí chưa kiểm chứng.


Đã bỏ gate độ dài/kết câu khi có tín hiệu, đưa viết tắt nghi vấn vào bất định và giữ bản gốc khi chưa rõ. Consent/budget vẫn áp dụng. Verifier có system instruction phân biệt dữ liệu với chỉ dẫn, kiểm tra literal/whitespace và confidence hữu hạn; low-confidence không sửa output. Không khẳng định chống mọi prompt injection hoặc chất lượng ngữ nghĩa model thật. Các dòng “chưa triển khai” còn lại là lịch sử draft.

Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.
