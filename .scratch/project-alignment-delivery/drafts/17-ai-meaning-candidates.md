# 17: Tích lũy bằng chứng và tự tái sử dụng nghĩa AI theo ngữ cảnh

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Priority: P1
Type: implementation
Implementation: hoàn tất mã và kiểm thử phạm vi yêu cầu 2026-09-09; chưa triển khai/nghiệm thu trên SQL Server production

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): D-03–06, D-10; AC-14.

## Vấn đề cần giải quyết

Đường ghi nghĩa mới nằm ngoài workspace; proposal chưa lưu đủ bằng chứng; review_notes bị bỏ ở nhánh chưa duyệt.

## Vì sao quan trọng

Admin cần duyệt nghĩa mới mà không phải đọc lịch sử riêng hoặc tin một chuỗi AI không ngữ cảnh.

## Kết quả mong muốn / What to build

Từ khó được AI xử lý ngay trong phiên; hệ thống tích lũy bằng chứng độc lập và tự cho dùng nghĩa theo ngữ cảnh khi đủ điều kiện. Admin xử lý ngoại lệ, duyệt theo nhóm và kiểm tra mẫu.

## Ràng buộc

Chờ schema/mục đích sử dụng được xác minh; không xây pipeline training; không tự áp dụng nghĩa toàn cục chỉ từ một đề xuất AI.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [ ] Ứng viên từ kết quả suy đoán giữ nguồn/ngữ cảnh/mức tin cậy phù hợp; việc đã áp dụng cho phiên hiện tại không tự duyệt nghĩa dùng chung.

- [ ] Luồng workspace thật qua fake AI tạo ứng viên mới đúng nghĩa/nguồn và bằng chứng phù hợp.
- [ ] Tự chuyển ứng viên sang dùng có điều kiện theo bằng chứng; ngữ cảnh khác không bị cưỡng ép. Có trạng thái/audit và cơ chế thu hồi.
- [ ] Thực hiện toàn bộ tiêu chí trong [chính sách dùng chung đã chốt](../shared-meaning-policy.md), gồm ngoại lệ, thao tác nhóm, kiểm tra mẫu và hiệu lực cache.
- [ ] Admin xem bằng chứng tối thiểu mà không có quyền đọc toàn lịch sử user.
- [ ] Call trùng/cache-hit không tạo bản ghi không kiểm soát; không âm thầm mất proposal khi lưu thất bại.
- [ ] Chỉ lưu và dùng output trong phạm vi đã chốt từ điều tra hosted trial.

## Blocked by

- [14 — Tự gọi AI cho phần khó sau dataset, kể cả câu ngắn](14-automatic-ai-routing.md)
- [Xác minh môi trường và dữ liệu vận hành](../../project-fit-wayfinding/issues/04-runtime-data.md)
- [Chốt phạm vi hosted trial](../../project-fit-wayfinding/issues/08-trial-boundary.md)

## Khu vực có thể ảnh hưởng

Live AI result; PendingAbbreviationService/repository; pending schema; AdminModerationPage; integration tests.

## Comments

### Hoàn tất phạm vi được giao — 2026-09-09

Đã triển khai candidate/evidence/audit, ngưỡng 3 request + 2 user production hoặc 3 session dev, scope theo ngữ cảnh, conflict, API/UI admin và revoke có revision/cache invalidation. Kiểm thử API live với fake AI xác minh tạo → reuse → revoke và bảo toàn dataset-only. Chi tiết, phép đo và giới hạn tại [biên bản nghiệm thu](../../../docs/tickets-17-20-21-verification.md). Các ghi chú “chưa triển khai” bên dưới là lịch sử; nghiệm thu model thật, tải và SQL Server production không được đánh dấu hoàn tất từ test giả lập.

### Chốt tự động theo bằng chứng — 2026-09-07

Chủ project chấp thuận [chính sách dùng chung mới](../shared-meaning-policy.md): không bắt admin duyệt mọi nghĩa; triển khai dùng có điều kiện trước, đo chất lượng để hiệu chỉnh tự xác nhận. Các ghi chú “chưa duyệt không dùng chung” bên dưới là lịch sử đã được thay thế. Không đánh dấu implementation hoàn tất bằng việc cập nhật ticket.

### Cập nhật mục tiêu — 2026-09-07 (sau tích hợp Nemotron)

Nghĩa AI suy đoán được dùng trong phiên kể cả dưới ngưỡng; khác với việc ghi ứng viên và duyệt dùng chung. Review lưu nguồn/ngữ cảnh/confidence, không tự xuất bản nghĩa suy đoán. Ticket này chưa hoàn tất chỉ vì chuẩn hóa đã hoạt động.

Áp dụng [hồ sơ thay đổi và checklist review tổng thể](../teencode-policy-change.md). Ghi chú trái chính sách mới bên dưới là lịch sử; không tự đánh dấu các tiêu chí chưa kiểm chứng.


Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.

