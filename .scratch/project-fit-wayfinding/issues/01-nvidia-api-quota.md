# Kimi K3 trên NVIDIA: hợp đồng API và giới hạn có thể xác minh

Parent: ../map.md
Labels: wayfinder:research
Type: research
Wayfinding Status: resolved
Assignee: Codex — research NVIDIA API
Blocked by: 

## Question

Tài liệu NVIDIA chính thức hiện xác nhận những gì về model Kimi K3, endpoint, tham số, định dạng phản hồi, reasoning, JSON, lỗi/quota và latency? Những kết luận nào của review trước cần sửa hoặc rút lại? Phần nào chỉ có thể kiểm chứng bằng tài khoản thật?

Phân biệt hỗ trợ API được tài liệu hóa, khả năng tương thích client GLM trong repository, và quota thực tế của tài khoản. Không gọi inference, không dùng key, không yêu cầu đoạn Python lúc này. Kết quả không được tự quyết định thay người dùng về provider hoặc ngân sách.

## Comments

Nguồn: các điểm UNCERTAIN và câu hỏi còn mở trong review mức độ phù hợp của project, cuộc trao đổi ngày 2026-09-06.

## Answer

Đã xác minh model `moonshotai/kimi-k3` và hợp đồng NVIDIA; client hiện có tham số GLM chưa chứng minh tương thích K3 (top_p, thinking flags, JSON mode), chưa xử lý vòng đời 202 được tài liệu hóa. Không có căn cứ khẳng định free tier ít limit hơn Gemini. Quota tài khoản, latency, JSON thực tế và chất lượng tiếng Việt vẫn cần đo được cho phép; không gọi API trong phiên này.

Điểm mới cần làm rõ về mục đích pilot: điều khoản trial liên kết từ model card giới hạn internal testing/evaluation, không mặc định cho công việc thực của end-user; dữ liệu công khai vẫn có thể chứa thông tin cá nhân. Không thay provider/ngân sách thay người dùng.

Nguồn chính thức và đối chiếu code: [research artifact](../assets/nvidia-api-quota.md). `resolved` nghĩa là câu hỏi tài liệu đã trả lời và ranh giới bằng chứng đã rõ, không có nghĩa quota tài khoản đã được đo.
