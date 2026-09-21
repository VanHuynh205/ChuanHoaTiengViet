# Xác nhận những nơi đang sử dụng project

Parent: ../map.md
Labels: wayfinder:task
Type: task
Mode: HITL
Wayfinding Status: resolved
Assignee: unassigned
Blocked by:

## Question

Ngoài bản project trên máy hiện tại, có deployment hoặc script/công cụ nào đang gọi API, đọc/ghi database hoặc sử dụng dataset của project không? Cần chủ project chỉ ra vị trí/công dụng để kiểm tra đúng môi trường và quyết định phạm vi capability. Không cần secret hoặc Python gọi AI.

## Comments

### Phạm vi hiện tại được chủ project xác nhận

Tiến trình hiện tại chỉ chạy trên máy này; dataset đều trong project. Không cần giải pháp quota nhiều host cho 12. Chưa có danh sách cụ thể script/công cụ khác trên cùng máy đọc/ghi SQL/dataset, nên không dùng câu trả lời này để cho phép xóa endpoint/bảng hoặc kết luận điều tra consumer cho ticket 18 đã hoàn tất.

### Câu trả lời mới của chủ project — 2026-09-06

Chủ project xác nhận "các dataset đều trong project, API sẽ lấy Kimi K3 free ở Nvidia build". Đây là xác nhận vị trí dataset và provider dự kiến, chưa xác nhận không có consumer ngoài hoặc topology. Đã hỏi tiếp liệu chỉ có một backend trên máy này và không có consumer dùng chung API/SQL/key hay có nhiều worker/instance. Không suy diễn câu trả lời thành topology một process.

Ngày 2026-09-06, phiên thực hiện tiếp đã hỏi vị trí deployment/script/consumer ngoài và số instance/worker dự kiến. Quan sát local được lưu trong [bằng chứng runtime](../assets/runtime-observation-2026-09-06.md); không đủ để kết luận không có consumer ngoài. Giữ open chờ thông tin chủ project.

Tách từ kiểm kê capability trong repository: không thể xác minh sự vắng mặt của consumer ngoài bằng tìm kiếm source. Câu hỏi đã gửi cho chủ project; chưa có câu trả lời cụ thể. Không tự coi “tiếp tục” là xác nhận chỉ có local.

## Answer — 2026-09-08

Chủ project trả lời trực tiếp câu hỏi trong phiên ticket 18: “Chỉ backend/frontend của project”. Đủ chốt consumer hiện tại cho 18, không có công cụ ngoài cần bảo toàn contract riêng. Các script nội bộ vẫn giữ nguyên endpoint/định dạng tương thích. Nếu topology/consumer đổi, phải đánh giá lại.
