# 12: Áp dụng ngân sách AI chung và giới hạn theo user

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Implementation: complete — theo yêu cầu thực hiện mới, phạm vi một host / fake AI
Evidence: ../execution-evidence.md
Priority: P1
Type: implementation

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): A-04–06; AC-20.

## Vấn đề cần giải quyết

Semaphore theo request và cooldown sau 429 chưa kiểm soát tổng request của nhiều user.

## Vì sao quan trọng

Tăng tự động hóa mà không có budget chung có thể cạn quota hoặc một user chiếm hết dịch vụ.

## Kết quả mong muốn / What to build

Mọi lần gọi AI đi qua ngân sách tổng và theo user phù hợp môi trường được xác minh.

## Ràng buộc

Chờ kết luận topology từ wayfinding; không mặc định Redis/microservices hoặc đồng nhất counter process với quota tài khoản.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [x] Hai user gọi đồng thời không vượt ngân sách tổng đã cấu hình cho topology đã chốt.
- [x] Một user chạm hạn mức không khiến user khác mất phần ngân sách được phép.
- [x] Request trùng được tái sử dụng khi hợp lệ; timeout/retry có giới hạn; không rò output qua cache.
- [x] Quota từ chối tạo trạng thái theo contract AI; dùng hạn mức giả lập để test, không bịa hạn mức nhà cung cấp.

## Blocked by

- [05 — Hiển thị đúng phạm vi và lý do chưa được AI kiểm tra](05-truthful-ai-status.md)
- [Xác minh môi trường và dữ liệu vận hành](../../project-fit-wayfinding/issues/04-runtime-data.md)

## Khu vực có thể ảnh hưởng

AI admission/client/budget/cache; request identity; runtime config; multi-user tests.

## Comments

Đã thêm ledger SQLite chia sẻ local worker, scope user từ auth dependency, deadline/retry tính từng attempt, gộp request trùng cùng user và scope cache. Có test hai tiến trình riêng và API xác thực hai tài khoản. Topology của wayfinding 04 đã đủ cho ticket này; backup/cleanup/schema còn mở không liên quan admission. Chi tiết giới hạn chuyển máy nằm ở docs/ai-runtime.md. Các dòng “chưa triển khai” còn lại là lịch sử bản draft.

Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.
