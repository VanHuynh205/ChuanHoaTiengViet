# Hiệu lực cập nhật từ điển

Phạm vi triển khai ticket 18: backend/frontend của project trên **một host**, các
worker dùng cùng `Settings.data_dir`. Chủ project xác nhận không có consumer khác
trực tiếp đọc/ghi SQL hoặc dataset. Không hỗ trợ nhiều host bằng cơ chế này.

## Nguồn dữ liệu và phiên bản

SQL giữ các mục đã được admin chỉnh sửa; dữ liệu bootstrap vẫn bổ sung các mục
chưa có trong SQL. `approved_abbreviations.json` là bản xuất phục vụ đường đọc
JSON hiện có, không được dùng để ghi đè quyết định admin khi seed lại.

`<data_dir>/runtime/dictionary-state.sqlite3` lưu phiên bản và trạng thái xuất JSON.
Các worker phải cùng dùng tệp này và có quyền ghi thư mục runtime. Không xóa/đặt
lại tệp khi các worker đang chạy. Khi di chuyển project, dùng cùng đường dẫn dữ
liệu cấu hình cho tất cả worker; không sao chép từng worker một phiên bản riêng.

Sau khi SQL commit, xuất JSON được tuần tự hóa qua khóa SQLite; snapshot được
đọc trong khóa để tránh bản xuất cũ ghi đè bản mới. Phiên bản tăng cả khi xuất JSON
lỗi. Live-data/bootstrap/segment/semantic cache dựa trên phiên bản; phản hồi AI
đang chạy với phiên bản cũ bị loại, kể cả snapshot tiến độ. Lượt gọi AI cùng prompt
nhưng khác phiên bản không dùng chung request đang chạy.

Frontend gửi lại request khi nhập, không phục vụ kết quả cũ chỉ từ cache trình
duyệt. Workspace kiểm tra phiên bản mỗi 5 giây và khi lấy lại focus để làm mới
input đang mở; việc kiểm tra không gọi AI. Khi phiên bản đổi, việc chuẩn hóa lại
vẫn tuân theo lựa chọn cho phép AI và ngân sách. 5 giây là chu kỳ kiểm tra, không
phải cam kết thời gian hoàn tất dưới mọi điều kiện mạng hoặc tab chạy nền.

## Khi lưu không đồng bộ hoàn toàn

- `dictionary_sync.status=synced`: đã xuất JSON và phát hành phiên bản.
- `export_failed`, `database_committed=true`: SQL đã lưu; JSON chưa cập nhật. UI
  báo rõ, giữ trạng thái qua reload và có nút thử đồng bộ lại. SQL mới vẫn là nguồn
  khi SQL sẵn sàng; không coi JSON cũ là bản dự phòng cập nhật nếu SQL cũng lỗi.
- HTTP 503 kèm `database_committed=true`: SQL đã lưu nhưng không xác nhận được
  phiên bản hoặc đọc lại. Không gửi lại thao tác thêm nghĩa chỉ vì thấy 503. Kiểm
  tra quyền/dung lượng runtime, đọc lại mục từ và thử đồng bộ lại.

API:

- User có đăng nhập: `GET /api/dictionary/revision`.
- Admin: `GET /api/admin/dictionary/sync-status` và
  `POST /api/admin/dictionary/retry-export` (chỉ xuất lại, không lưu lại nghĩa).

Nếu tiến trình bị dừng giữa SQL commit và phát hành phiên bản, cần chạy retry-export
để đối chiếu lại trước khi nghiệm thu phục hồi. SQL và SQLite/JSON không phải một
transaction phân tán; ticket này không tuyên bố phục hồi crash tự động hoặc backup.

## Kiểm thử cô lập

Từ root: `.venv/Scripts/python.exe -m pytest backend/tests/test_dictionary_consistency.py -q`.
Test dùng hai process độc lập, FastAPI/JWT/live service/cache thật và repository
kiểm thử SQLite trong thư mục tạm; không ghi SQL vận hành.

Từ frontend: `npx playwright test --config playwright.dictionary.config.ts`.
Chạy Edge headless với ba browser contexts, server fixture ở 8018 và Vite ở 5188;
không tái sử dụng backend đang chạy và không gọi NVIDIA. Fixture chỉ chứa dữ liệu
tổng hợp, không dùng như server vận hành.
