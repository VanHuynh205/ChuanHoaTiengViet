# Ticket 18 — bằng chứng nghiệm thu 2026-09-08

## Phạm vi và blocker

Chủ project yêu cầu làm ticket 18 và xác nhận chỉ backend/frontend của project
đọc/ghi dữ liệu. Topology một host đã được xác nhận trước; không giả định một
worker. Giữ cơ chế SQL ưu tiên cho mục admin chỉnh sửa và JSON bootstrap/export
đang có. Không đổi SQL schema, seed DB vận hành, xóa endpoint/dataset hoặc gọi AI thật.
Backup/restore/retention trong wayfinding 04 vẫn mở, không được coi là đã nghiệm thu.

## Trước và sau

- Trước: export ném OSError sau SQL commit làm save báo lỗi và bỏ qua invalidation.
  Test đã tái hiện thất bại trước sửa. Nay giữ kết quả đã lưu, trả `dictionary_sync`,
  phát hành revision và lưu `export_failed`; đọc trạng thái/repair được qua API admin.
- Trước: cache giữa worker chỉ có generation trong process; frontend có thể trả
  cache mà không hỏi server. Nay phiên bản dùng chung gắn với cache và kiểm tra
  phiên bản trong workspace; request lặp luôn revalidate backend.
- AI cache và coalescing phân biệt revision; câu trả lời và snapshot tiến độ
  từ phiên bản cũ không được áp dụng sau khi phát hiện phiên bản thay đổi.
- Seed từng chỉ bảo vệ một phần alternative list, vẫn có thể ghi đè nghĩa chính
  admin hoặc phục hồi nghĩa đã bỏ. Test bổ sung đã đỏ trước sửa; bootstrap nay
  bỏ qua bản ghi do người duyệt đã xác nhận, admin edit vẫn được thay thế rõ ràng.
- Lỗi read-back sau commit có HTTP 503 riêng kèm `database_committed=true`, tránh
  báo sai là SQL chưa lưu. Không gửi lại mutation để sửa lỗi export.

## Các bằng chứng đã chạy

1. Hai process độc lập, mỗi process có FastAPI/JWT và cache riêng, cùng repository
   kiểm thử trong thư mục tạm. Làm nóng live-data/segment cache rồi admin lưu ở một
   worker; cả hai trả nghĩa mới ngay ở request tiếp theo. Bao phủ export thành công
   và export cố tình thất bại; cùng đọc được revision và trạng thái bền vững.
2. API xác thực: anonymous không đọc revision; user đọc revision nhưng không đọc
   trạng thái admin hoặc gọi repair; admin đọc được. Test read-back lỗi xác nhận
   response nói rõ SQL đã commit.
3. Fake AI trả muộn sau revision thay đổi: không ghi đè output, cả response thường
   lẫn NDJSON. Verifier cache và admission không tái sử dụng phản hồi phiên bản cũ.
4. **Playwright/Edge: 1 test đạt qua 3 browser contexts.** Hai workspace đã mở nhận
   nghĩa mới khi admin sửa trên UI; giả lập JSON export lỗi vẫn cập nhật được,
   admin reload còn cảnh báo và retry-export thành công. Backend thật với data/auth
   repositories cô lập, không phải SQL production và không chứng minh tải production.
5. Frontend: **35 tests đạt**, TypeScript/Vite build đạt. Ruff/Mypy đạt (14-file scope).
   Backend toàn suite cuối: **468 passed, 1 skipped, 39 subtests** (29.84 giây).

## Giới hạn nghiệm thu

Chấp nhận ticket 18 cho topology một host và dữ liệu/consumer đã xác nhận. Chưa có
transaction nguyên tử xuyên SQL/JSON/SQLite khi process crash; quy trình repair
được mô tả trong [hướng dẫn vận hành](../../docs/dictionary-consistency.md).
Các trạng thái nghĩa AI tự dùng có điều kiện chưa được xây ở ticket 17; chúng phải
dùng revision/invalidation khi triển khai, chưa được tuyên bố đã kiểm chứng ở đây.
Ticket 19/17/20/21 chưa được hoàn tất bởi thay đổi này.
