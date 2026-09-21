# 05: Hiển thị đúng phạm vi và lý do chưa được AI kiểm tra

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Priority: P0
Type: implementation

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): R-07–10, A-06; AC-03–05.

## Vấn đề cần giải quyết

0 verified chunk vẫn có thể semanticVerified=true; UI nói chính xác tuyệt đối hoặc đã đồng bộ dù AI bị bỏ qua.

## Vì sao quan trọng

Người dùng phải biết giới hạn trước khi tin hoặc copy kết quả.

## Kết quả mong muốn / What to build

Response và UI phân biệt không cần AI, chưa được kiểm tra, kiểm tra một phần, lỗi/quota và thực sự đã kiểm tra.

## Ràng buộc

Không đổi provider, thuật toán chọn nghĩa hoặc xây quota ledger. Tận dụng contract hiện có, mở rộng tối thiểu.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [x] UI giải thích `ai_inferred_meaning` là nghĩa AI suy đoán có thể sai; component test đã đạt.
- [ ] Review tổ hợp nhiều chunk: không gắn nhãn chắc chắn cho phần suy đoán hoặc làm mất phạm vi chưa xử lý.

- [ ] Verifier trả 0 chunk và confidence cao không tạo trạng thái AI verified.
- [ ] Một số chunk đã kiểm tra không làm toàn văn được gắn nhãn hoàn tất AI.
- [ ] Quota, timeout, provider chưa cấu hình có trạng thái/lý do rõ; không mất input hoặc output hiện có.
- [ ] UI không biến confidence model thành tỷ lệ chính xác đã kiểm định; cache-hit chỉ xác nhận phạm vi có bằng chứng tương thích.

## Blocked by

None (can start immediately sau khi ticket được duyệt).

## Khu vực có thể ảnh hưởng

Semantic verifier result; live response/schema/types; status/banner/output pane; AI fake tests.

## Comments

### Chính sách dùng chung đã chốt — 2026-09-07

Nguồn tái sử dụng nghĩa có điều kiện phải phân biệt với dataset đã xác nhận; không biến bằng chứng lặp thành cam kết chính xác. Xem [chính sách và nghiệm thu](../shared-meaning-policy.md). Đây là yêu cầu mới cần kiểm chứng, không tự đóng ticket.

### Cập nhật mục tiêu — 2026-09-07 (sau tích hợp Nemotron)

Phân biệt kết quả đã áp dụng theo suy đoán AI với phần giữ nguyên/chưa kiểm tra. Review `uncertain/ai_inferred_meaning`, cache và phạm vi nhiều chunk; không gọi suy đoán là chính xác.

Áp dụng [hồ sơ thay đổi và checklist review tổng thể](../teencode-policy-change.md). Ghi chú trái chính sách mới bên dưới là lịch sử; không tự đánh dấu các tiêu chí chưa kiểm chứng.


Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.

