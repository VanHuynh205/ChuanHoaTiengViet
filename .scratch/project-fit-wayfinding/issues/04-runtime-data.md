# Trạng thái triển khai, schema và vòng đời dữ liệu thực tế

Parent: ../map.md
Labels: wayfinder:task
Type: task
Wayfinding Status: open
Assignee: unassigned
Blocked by: 

## Question

Xác minh bằng thao tác chỉ đọc: có bao nhiêu instance/worker; schema thực tế so với init_schema.sql; nguồn dữ liệu có thẩm quyền giữa SQL và JSON; cache/version khi admin cập nhật; backup/restore; lịch cleanup và retention; đường dùng pending và history.

Không in secret, không chạy migration/seed/cleanup, không gọi inference. Không sửa cấu hình hoặc dừng dịch vụ. Tách sự thật tìm thấy trong code, quan sát được ở môi trường và điều chưa có quyền truy cập/bằng chứng. Nếu kết nối DB cần quyền bổ sung thì hỏi đúng bước đó, không tìm cách vượt quyền.

## Comments

### Gate ticket 18 — 2026-09-08

Đủ phạm vi cho ticket 18: một host đã xác nhận, chủ project xác nhận chỉ backend/frontend của project. Giữ SQL ưu tiên cho mục đã chỉnh và JSON bootstrap/export, không đổi schema. Phiên bản SQLite dùng chung data_dir được kiểm chứng bằng hai process/API và browser cô lập. [Bằng chứng 18](../../project-alignment-delivery/ticket-18-evidence.md). Giữ điều tra này open cho backup/restore/retention và đối chiếu schema đầy đủ; không coi các phần đó đã được giải quyết.

### Phạm vi runtime đã xác nhận trong phiên thực hiện

Chủ project xác nhận tiến trình hiện tại chỉ chạy trên máy này và yêu cầu giảm lỗi khi chuyển máy. Đủ bằng chứng chọn admission dùng SQLite trên một host, chia sẻ giữa các worker qua cùng đường dẫn; không giả định chỉ có một worker. Phần topology cần cho ticket 12 đã được trả lời. Backup/restore, lịch cleanup và đối chiếu schema đầy đủ vẫn mở cho các quyết định dữ liệu; không dùng các phần đó để chặn ticket 12 vốn không sửa SQL/dataset. Xem [hướng dẫn vận hành](../../../docs/ai-runtime.md).

### Điều tra 2026-09-06

Đã kiểm tra runtime và SQL metadata chỉ đọc; xem [bằng chứng](../assets/runtime-observation-2026-09-06.md) và [probe tái lập](../assets/runtime_probe.py). Có đủ 16 tên bảng khai báo; chưa xác minh toàn bộ schema, topology mục tiêu, cleanup hay backup/restore. Giữ open vì thiếu bằng chứng, không coi launcher một process là topology đã chốt.

Nguồn: các điểm UNCERTAIN và câu hỏi còn mở trong review mức độ phù hợp của project, cuộc trao đổi ngày 2026-09-06.

### Bằng chứng ban đầu từ review trước — cần đối chiếu môi trường

- Schema khai báo `sp_cleanup_expired_data`; có procedure không chứng minh có lịch chạy. Chưa chạy procedure.
- Admin save commit SQL rồi export JSON và invalidate cache trong process; đây là sự thật trong code, chưa phải quan sát lỗi ở môi trường.
- Live-data cache có TTL và generation trong process; segment cache có generation nhưng không thấy TTL. Cần kiểm tra kết quả giữa worker/trình duyệt sau thay đổi từ điển.
- Chưa kết nối SQL để so schema hoặc xác minh backup/restore. Không coi số bảng trong script là trạng thái database thật.
