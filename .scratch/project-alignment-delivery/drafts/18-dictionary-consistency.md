# 18: Áp dụng cập nhật từ điển nhất quán sau khi admin lưu

Status: needs-triage
Publication: draft — chờ duyệt breakdown
Priority: P1
Type: implementation
Implementation: complete — topology một host đã xác nhận, nghiệm thu cô lập
Evidence: ../ticket-18-evidence.md

## Nguồn

[Specification đã chấp thuận](../../project-fit-wayfinding/spec.md): D-08–10; AC-15.

## Vấn đề cần giải quyết

SQL commit, export JSON và cache invalidation không có trạng thái kết quả chung; cache trình duyệt/worker có thể tiếp tục dùng dữ liệu cũ.

## Vì sao quan trọng

Nghĩa admin đã sửa phải có hiệu lực thực, không chỉ báo lưu thành công.

## Kết quả mong muốn / What to build

Sau lưu, lần chuẩn hóa tiếp theo dùng dữ liệu hiệu lực; lỗi đồng bộ có trạng thái rõ và có thể xác định kết quả.

## Ràng buộc

Phạm vi đã xác nhận: chỉ backend/frontend của project trên một host, worker dùng chung data_dir. Giữ SQL ưu tiên cho mục admin chỉnh sửa, JSON bootstrap/export tương thích; không thêm distributed store hoặc sửa SQL schema.

Giữ kiến trúc hiện có. Không mở rộng sang các capability ALIGNED. Nghiệm thu qua workspace/backend thật trong môi trường cô lập, fake AI cho lỗi/quota/trả muộn và API xác thực cho quyền. Fake AI không chứng minh chất lượng model thật. Không chạy inference ngoài phạm vi được phép.

## Tiêu chí chấp nhận

- [x] Hai phiên user không tiếp tục nhận vô hạn kết quả từ điển cũ sau admin cập nhật.
- [x] Test theo topology đã xác minh bao phủ cache-hit và worker/trình duyệt khác.
- [x] Lỗi export sau ghi DB không báo sai rằng toàn bộ thao tác chưa xảy ra; có thể đọc lại trạng thái chính xác.
- [x] Bootstrap vẫn không ghi đè quyết định đã duyệt; không biến giữ nguyên hành vi này thành refactor riêng.

## Blocked by — đã giải quyết phần cần cho ticket 18

- [Xác minh môi trường và dữ liệu vận hành](../../project-fit-wayfinding/issues/04-runtime-data.md)
- [Kiểm kê consumer ngoài repository](../../project-fit-wayfinding/issues/09-external-consumers.md)

## Khu vực có thể ảnh hưởng

Dictionary save/pending service; JSON export; live-data/segment/frontend cache; admin save response.

## Comments

### Hoàn tất ticket 18 — 2026-09-08

Đã sửa code và nghiệm thu: phiên bản chung giữa worker, revalidate frontend, trạng thái SQL đã lưu/JSON lỗi và repair, loại AI trả muộn, bảo vệ quyết định admin khi seed. Test hai process và Playwright ba browser contexts đạt. Xem [bằng chứng](../ticket-18-evidence.md) và [vận hành](../../../docs/dictionary-consistency.md). Không tự đóng các phần backup/restore/retention hoặc ticket kế tiếp. Ghi chú “chưa triển khai” bên dưới là lịch sử.

### Chính sách dùng chung đã chốt — 2026-09-07

Hiệu lực nghĩa tự dùng có điều kiện cũng phải có phiên bản. Thu hồi phải vô hiệu cache/request đang chạy; không để bootstrap hoặc bằng chứng cũ tự khôi phục nghĩa. Xem [chính sách và nghiệm thu](../shared-meaning-policy.md). Đây là yêu cầu mới cần kiểm chứng, không tự đóng ticket.

Chưa triển khai. Các blocker điều tra phải được giải quyết trước khi chọn giải pháp phụ thuộc; không dùng ticket này để tự điền giả định.

