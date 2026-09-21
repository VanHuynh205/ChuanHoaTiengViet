# Ranh giới giữa đánh giá nội bộ và sử dụng kết quả cho công việc thực tế

Parent: ../map.md
Labels: wayfinder:grilling
Type: grilling
Wayfinding Status: resolved
Assignee: unassigned
Blocked by: 01, 02

## Question

Phạm vi đã chốt là nhóm nhỏ có đăng nhập, nhưng nhóm này chỉ đánh giá nội bộ hay sử dụng kết quả cho công việc thực tế? Làm rõ loại dữ liệu được gửi và cách thể hiện giới hạn thử nghiệm trước khi coi NVIDIA Build miễn phí là integration phù hợp.

Không tự thay provider, ngân sách hoặc mục tiêu của chủ project. Không suy rằng public text luôn không chứa thông tin cá nhân. Nguồn điều khoản và ngoại lệ nằm ở hai nghiên cứu NVIDIA.

## Comments

### Phạm vi đợt tích hợp được xác nhận — 2026-09-07

Chủ project đã xác nhận rõ đợt tiếp theo chỉ tích hợp và kiểm thử nội bộ bằng văn bản tổng hợp, chưa dùng output cho công việc thực tế của người tiêu dùng. Phạm vi này cho phép thực hiện ticket 13 và smoke giới hạn; không đồng nghĩa đã xác nhận quyền phục vụ người tiêu dùng bằng hosted trial. Các câu hỏi về triển khai cho người tiêu dùng thuộc cổng quyết định trước giai đoạn đó.

## Answer

Phạm vi hiện tại: kiểm thử kỹ thuật nội bộ, dữ liệu tổng hợp, không deploy hoặc bật AI cho công việc thực tế của người dùng. Mục tiêu dài hạn vẫn là dịch vụ người tiêu dùng; quyền/điều khoản cho giai đoạn đó chưa được xác minh. Câu hỏi phạm vi của đợt tích hợp này đã được chủ project trả lời.

### Làm rõ mục đích của dự án — 2026-09-07

Chủ project xác nhận kết quả chuẩn hóa do user sử dụng; dự án cung cấp dịch vụ cho người tiêu dùng, không có ý thu thập dữ liệu chuẩn hóa cho mục đích cá nhân khác. Ghi nhận đây là mục đích của ứng dụng, không phải điều khoản bổ sung của NVIDIA. Không tự kết luận tài khoản có hoặc không có quyền đặc biệt. Phạm vi công việc thực tế đã rõ; câu hỏi điều kiện hosted service vẫn chưa có bằng chứng mới để đóng.

### Disclosure do chủ project cung cấp

Chủ project lấy model ở Free Endpoint và cung cấp nội dung: không tải thông tin bí mật hoặc dữ liệu cá nhân; sử dụng được ghi lại cho bảo mật và cải thiện sản phẩm/dịch vụ NVIDIA; dữ liệu phiên phục vụ cải thiện không liên kết danh tính hoặc mã định danh cố định. Đây là bằng chứng từ màn hình tài khoản do chủ project báo lại, không phải kết quả kiểm tra trực tiếp của agent. Chưa có nội dung cho phép dùng output hosted trial vào công việc thực tế; giữ câu hỏi quyền sử dụng mở, không diễn giải disclosure logging thành quyền production hoặc zero-retention. Không yêu cầu key trong bước này.

### Câu trả lời mới của chủ project — 2026-09-06

Chủ project xác nhận: "dùng kết quả cho công việc thực tế" và API dự kiến là Kimi K3 miễn phí trên NVIDIA Build. Mục đích đã rõ, nhưng chưa có bằng chứng quyền tài khoản cho phép phạm vi đó. Hồ sơ `assets/nvidia-data-terms.md` ghi API Trial Terms giới hạn đánh giá nội bộ; lần mở lại PDF bằng web tool trong phiên này lỗi HTTP 500 nên chưa xác minh lại trực tuyến. Đã hỏi về quyền/điều khoản riêng của tài khoản, không yêu cầu key. Giữ open đến khi xác định sự phù hợp hoặc quyết định phương án; không tự đổi provider. Ticket 13 chưa đủ điều kiện, chất lượng model thật không chặn ticket fake AI.

Ngày 2026-09-06, phiên thực hiện tiếp đã hỏi lại mục đích đánh giá nội bộ hay công việc thực tế và loại dữ liệu. Chưa có câu trả lời mới tại thời điểm ghi; giữ open, chưa bắt đầu integration Kimi.

Đã gửi câu hỏi cho chủ project ngày 2026-09-06. Chưa nhận câu trả lời cụ thể; “tiếp tục” không được coi là lựa chọn một phương án.
