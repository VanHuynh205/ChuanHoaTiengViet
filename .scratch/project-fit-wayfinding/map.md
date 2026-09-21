# Làm rõ các điểm chưa chắc chắn về mức độ phù hợp của project

Labels: wayfinder:map

## Destination

Giải quyết các điểm UNCERTAIN của review để chốt hành vi và ràng buộc mong muốn của project trước khi lựa chọn giải pháp triển khai. Phân biệt điều đã xác minh, quyết định của chủ project, giả định tạm thời và bằng chứng chỉ thu được sau tích hợp.

## Notes

- [Specification chuẩn hóa tiếng Việt](spec.md) tổng hợp trạng thái mong muốn theo yêu cầu to-spec; việc xuất bản và xác nhận seam kiểm thử không tự đóng các câu hỏi điều tra còn mở.
- Chỉ điều tra và lập quyết định; không sửa implementation, không tạo implementation ticket, không triển khai.
- Nguồn mục tiêu: Q1–Q16 đã được chủ project đồng ý trong cuộc trao đổi; cập nhật cuối cùng chọn Kimi K3 qua NVIDIA Build thay Gemini.
- Giữ nguyên ưu tiên bảo toàn nghĩa → ngân sách → tốc độ; giữ nguyên phần bất định; dataset trước và AI tự động khi cần; nghĩa mới cần admin duyệt trước dùng chung.
- Hai chế độ nhập tay/dán văn bản; nhóm thử nghiệm nhỏ có đăng nhập; mục tiêu khoảng 5.000 từ; hai ô tương đương và highlight các loại thay đổi; lịch sử riêng theo user.
- User không sửa từ điển; admin không mặc định đọc lịch sử riêng. Văn bản gửi AI là công khai hoặc đã loại thông tin nhạy cảm, có thông báo và lựa chọn dataset-only.
- Khi bắt đầu code mới nhắc chủ project cung cấp Python gọi API. Không xin key hoặc gọi inference trong phiên lập bản đồ này.
- Skills: wayfinder; grilling và domain-modeling cho quyết định cần trao đổi; research cho nguồn bên ngoài; codebase-design nếu cần đánh giá vai trò abstraction. Theo yêu cầu không sửa tài liệu domain/ADR hiện có trong giai đoạn này; chỉ ghi hồ sơ ở effort này.
- Tracker: docs/agents/issue-tracker.md. Wayfinding Status quản lý tiến độ; không áp dụng nhãn triage implementation.
- Snapshot không có Git metadata: research được lưu trong assets/ của effort, không tạo branch giả hoặc khởi tạo Git.
- Các child ticket nằm trong issues/. Truy vấn frontier bằng Wayfinding Status, Blocked by và Assignee; không sao chép danh sách ticket mở vào map.
- Mỗi phiên chỉ giải quyết tối đa một ticket không phải research; phiên chart lập bản đồ và có thể chạy các research song song.

## Decisions so far

- 2026-09-08: [consumer ngoài](issues/09-external-consumers.md) đã chốt chỉ backend/frontend. [Ticket 18](../project-alignment-delivery/ticket-18-evidence.md) hoàn tất cho một host: SQL edit, JSON export có trạng thái và revision chung worker. Backup/restore/retention vẫn mở ở 04.

- 2026-09-07: chủ project chốt [tự dùng nghĩa AI theo bằng chứng/ngữ cảnh](../project-alignment-delivery/shared-meaning-policy.md), admin xử lý ngoại lệ và kiểm tra mẫu. Thay chính sách duyệt thủ công mọi nghĩa; chưa triển khai cơ chế, ngưỡng cần đo.

- 2026-09-07, sau ticket 13: chủ project đổi provider sang Nemotron và yêu cầu AI chủ động chuẩn hóa teencode bằng nghĩa hợp lý nhất, kể cả ngoài dataset/confidence thấp, có nhãn suy đoán. Xem [spec v1.1](spec.md) và [thay đổi/checklist review](../project-alignment-delivery/teencode-policy-change.md). Ghi chú giữ nguyên mọi bất định hoặc chọn Kimi phía trên là lịch sử; các điều tra chất lượng/trial không tự đóng.

- [Phạm vi thử Kimi nội bộ](issues/08-trial-boundary.md): chủ project xác nhận dùng văn bản tổng hợp và chưa dùng output cho công việc thực tế của người tiêu dùng trong đợt tích hợp 13. Đây không phải quyết định triển khai production.

- [Kimi K3 trên NVIDIA: hợp đồng API và giới hạn có thể xác minh](issues/01-nvidia-api-quota.md): model và hợp đồng có tài liệu; chưa chứng minh tương thích client GLM hoặc quota/latency tài khoản.
- [NVIDIA Build miễn phí: phạm vi sử dụng và xử lý dữ liệu](issues/02-nvidia-data-terms.md): hosted trial có ràng buộc mục đích và dữ liệu; cần quyết định phạm vi thử nghiệm, không hứa zero-retention/no-training.
- [Những capability chưa nối vào workspace có người sử dụng thực tế không?](issues/03-unused-capabilities.md): đã phân biệt caller nội bộ thật với bảng/wrapper chưa nối; xác nhận consumer ngoài còn ở ticket riêng, chưa quyết định xóa.

## Not yet specified

Những câu hỏi sản phẩm phát sinh nếu điều kiện hosted API, nguồn dữ liệu ngoài repository hoặc quan sát vận hành mâu thuẫn với phạm vi thử nghiệm đã chốt. Chỉ tách thành câu hỏi cụ thể khi có bằng chứng mới.

## Out of scope

- Sửa lỗi, đổi model/cấu hình, migration/seed/cleanup dữ liệu, deploy, tạo implementation ticket.
- Xây lại kiến trúc, thêm microservices, nhập/xuất file hoặc public API cho bên ngoài khi chưa có quyết định phạm vi.
- Đo inference Kimi thật hoặc yêu cầu Python/key trong phiên lập bản đồ này.
