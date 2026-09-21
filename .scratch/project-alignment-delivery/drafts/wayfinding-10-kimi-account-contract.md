# Xác minh hợp đồng Kimi trên tài khoản thực tế

Status: needs-triage
Publication: draft — dự kiến xuất bản thành wayfinding 10
Parent: ../../project-fit-wayfinding/map.md
Type: task
Wayfinding Status: open
Blocked by: 08 (Ranh giới hosted trial, trong nhóm project-fit-wayfinding)

## Question

Tài khoản được phép dùng model nào, quota/credit thực tế ra sao và hợp đồng request/response Kimi có đáp ứng luồng chuẩn hóa không?

## Vì sao quan trọng

Client hiện dựa trên GLM. Tài liệu model không chứng minh tham số, JSON, reasoning, phản hồi pending/truncated và giới hạn tài khoản tương thích.

## Kết quả và tiêu chí chấp nhận

- [ ] Ghi bằng chứng model/endpoint và giới hạn tài khoản; phân biệt số công bố, số quan sát và phần chưa biết.
- [ ] Khi bắt đầu giai đoạn tích hợp, nhắc chủ project cung cấp Python gọi API; không xin key hoặc gọi inference trong phiên lập ticket.
- [ ] Đối chiếu sample với contract chính thức; xác định JSON, reasoning, finish reason, pending/polling và lỗi cần xử lý; không mặc định tham số GLM.
- [ ] Nếu thử thật đã được phép, dùng dữ liệu tổng hợp và ngân sách giới hạn, ghi kết quả có thể tái lập mà không lộ key. Nếu chưa được phép, ghi blocker thay vì coi đã kiểm chứng.
- [ ] Trả kết luận đủ/thiếu điều kiện cho ticket tích hợp; không chỉnh application implementation.

## Khu vực liên quan

NVIDIA adapter, cấu hình provider, parser phản hồi; tài khoản do chủ project quản lý.

## Comments

### Quan sát tài khoản/endpoint — 2026-09-07

Đã có key phía server và quyền thử nội bộ do chủ project xác nhận. Hai probe Kimi tổng hợp giới hạn 60 giây đều timeout; chưa có response chứng minh model access/JSON/finish reason/quota. Không đóng điều tra chỉ vì đã có key hoặc fake tests pass. Chi tiết: [ticket 13 evidence](../kimi-13-evidence.md).

### Mẫu Python đã nhận — 2026-09-07

Đã nhận mẫu Free Endpoint từ chủ project, có model moonshotai/kimi-k3, reasoning_effort=max và SSE. Mẫu chứa placeholder NVIDIA_API_KEY, chưa có response thật hoặc quota tài khoản. Đã đối chiếu với client GLM: [bằng chứng](../../project-fit-wayfinding/assets/kimi-user-sample-2026-09-07.md). Web tool lỗi HTTP 500 khi mở lại reference chính thức; chưa đóng điều tra, chưa chỉnh adapter.

Nguồn: A-01/05/10/11 và Further Notes của specification; hai nghiên cứu NVIDIA đã có. Không lặp lại nghiên cứu chỉ để đổi tên model.
