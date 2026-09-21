# Bằng chứng nào đủ để chấp nhận chất lượng và hiệu năng thử nghiệm?

Parent: ../map.md
Labels: wayfinder:grilling
Type: grilling
Wayfinding Status: open
Assignee: unassigned
Blocked by: 

## Question

Với mục tiêu ưu tiên bảo toàn nghĩa, văn bản đến khoảng 5.000 từ và nhóm nhỏ, cần chốt bộ ví dụ, các loại lỗi không chấp nhận, cách đánh giá trường hợp bất định và tiêu chí tốc độ/quota trước khi chọn giải pháp.

54 test kỹ thuật đã pass trong review không phải benchmark sản phẩm. Chưa có số đo Kimi thật. Quyết định phải phân biệt tiêu chí nghiệm thu cần chốt bây giờ với số đo chỉ thu được sau tích hợp. Không tự bịa SLA, số user đồng thời hoặc tỷ lệ chính xác; không bắt người dùng cung cấp số liệu có thể đo từ môi trường.

## Comments

### Mục tiêu nghiệm thu cập nhật — 2026-09-07

Chủ project ưu tiên AI chủ động giải nghĩa teencode ngoài dataset/khi thiếu ngữ cảnh, áp dụng đề xuất hợp lệ dưới ngưỡng confidence với nhãn suy đoán. [Checklist review tổng thể mới](../../project-alignment-delivery/teencode-policy-change.md) bổ sung đo nhận diện bỏ sót, sửa sai nghĩa, cache/lịch sử/highlight và tổ hợp chunk chắc chắn/suy đoán/lỗi. Provider hiện là Nemotron; có smoke ngắn thành công, chưa phải benchmark hoặc SLA. Giữ điều tra mở; không dùng test fake hay số từ sửa được làm bằng chứng chất lượng ngôn ngữ.

Nguồn: các điểm UNCERTAIN và câu hỏi còn mở trong review mức độ phù hợp của project, cuộc trao đổi ngày 2026-09-06.

### Bằng chứng ban đầu

- Review đã chạy 54 test chọn lọc với mạng AI tắt, tất cả pass; chưa chạy toàn bộ E2E hoặc inference thật.
- Kiểm tra hàm độc lập đã tái hiện mất ranh giới đoạn khi xóa emoticon, sai khoảng cách quanh ngoặc/tỷ lệ số và viết hoa chữ trong URL; verifier giả lập `verified_chunks=0` vẫn có thể tạo `semanticVerified=true`.
- Các lỗi đã chứng minh này không còn là UNCERTAIN; không dùng ticket này để điều tra lại hoặc sửa chúng. Ticket chỉ chốt tiêu chuẩn bằng chứng cho chất lượng/hiệu năng còn chưa đo.
