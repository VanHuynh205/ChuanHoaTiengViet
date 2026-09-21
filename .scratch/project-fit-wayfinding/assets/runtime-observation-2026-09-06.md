# Runtime observation — 2026-09-06

## Quan sát chỉ đọc trên máy hiện tại

- Không thấy tiến trình Python/backend trong snapshot Win32_Process; không thấy listener trên 8000, 5173, 1433. SQL Server có tiến trình chạy; named instance vẫn kết nối được. Snapshot không chứng minh không có deployment ngoài máy hoặc port khác.
- Cấu hình hiệu lực: SQL Express, Windows authentication. Không xuất hostname, connection string, credential hoặc nội dung bảng người dùng.
- Probe `runtime_probe.py` thất bại trong sandbox với SQLSTATE 08001; chạy ngoài sandbox sau approval kết nối thành công.
- Database có đủ 16 tên bảng dbo được khai báo bằng CREATE TABLE trong init_schema.sql. Đã đọc metadata cột; chưa đối chiếu toàn bộ kiểu/cột/index/constraint/procedure, vì vậy không kết luận schema hoàn toàn tương đương.
- Có `sp_cleanup_expired_data`. Có 1 SQL Agent job toàn instance; chưa xác minh job này liên quan cleanup hoặc có lịch chạy hiệu lực.
- `msdb.dbo.backupset` không trả bản ghi cho database hiện tại; `restorehistory` trả MAX(restore_date)=NULL. Không chứng minh không có backup ngoài SQL hoặc lịch sử đã bị dọn. Chưa có bằng chứng restore thành công.
- Không chạy migration, seed, cleanup, inference; không sửa config hoặc dừng/khởi động dịch vụ.

## Sự thật từ source

- scripts/run_backend_dev.cmd và start_demo_servers.ps1 gọi uvicorn không truyền --workers. Đây là launcher local, chưa phải topology deployment được chủ project xác nhận.
- PendingAbbreviationService có live-data TTL 15s, shared bootstrap TTL 60s và generation trong process. Admin save gọi repository trước, rồi export JSON, rồi invalidate cache; export lỗi có thể ngăn invalidate. Chưa thử ghi dữ liệu vận hành.
- SQL và JSON cùng tham gia live data. Cần chủ project xác nhận nguồn có thẩm quyền và consumer ghi ngoài trước khi thay đổi đồng bộ.
- Code đã có semantic status/reason/chunk counts và dataset-only trong route dù draft 05/11 còn ghi chưa triển khai. Không dùng trạng thái draft để phủ nhận code hoặc coi mọi acceptance criterion đã đạt.
- Chạy `python -m pytest tests/test_semantic_verifier.py -q` tại backend: 20 passed; cảnh báo không ghi được pytest cache. Đây chỉ là regression verifier, chưa nghiệm thu toàn bộ ticket 05/11.

## Còn thiếu để ra quyết định

- Topology mục tiêu: deployment nào, số instance/worker, có chia sẻ quota tài khoản với consumer khác hay không.
- Consumer ngoài: cần chủ project xác nhận vị trí/công dụng hoặc xác nhận không có; tìm source không chứng minh sự vắng mặt.
- Trial: chỉ đánh giá nội bộ hay dùng kết quả cho công việc thực tế; loại dữ liệu được gửi.
- Nguồn dữ liệu có thẩm quyền, lịch cleanup/retention và bằng chứng backup/restore; chưa đóng wayfinding 04.

## Thứ tự đã được yêu cầu

Cập nhật từ chủ project: dataset đều trong project; dùng Kimi K3 free NVIDIA Build và dùng kết quả cho công việc thực tế. Chưa xác nhận topology hoặc consumer ngoài. Trial cần bằng chứng quyền phù hợp với mục đích này; lần xác minh lại PDF qua web lỗi HTTP 500. Đã gửi câu hỏi về topology và quyền tài khoản, chưa cần key.

Chỉ bắt đầu 12 khi đủ bằng chứng và dependency; tiếp theo 14 → 15 → 16. Chất lượng model thật không chặn nghiệm thu dùng fake AI. Ticket 13 đợi trial và điều tra hợp đồng Kimi; trước khi gắn Python gọi Kimi vào codebase phải báo chủ project cung cấp code và key. Chưa cần code/key trong bước quan sát này.
