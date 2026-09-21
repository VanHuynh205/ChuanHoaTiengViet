# Chính sách dùng chung nghĩa AI — chốt 2026-09-07

Authority: chủ project chấp thuận phương án tự động theo bằng chứng, admin xử lý ngoại lệ.
Implementation: đã triển khai phạm vi v1 theo yêu cầu trực tiếp 2026-09-09; chưa nghiệm thu SQL Server/model/tải production.

## Phạm vi v1 — cập nhật 2026-09-09

Ngưỡng do chủ project chỉ định: 3 request có context fingerprint khác nhau, kèm 2 user production hoặc 3 session development. Scope bảo thủ theo domain và hai từ lân cận; không tự nâng confirmed. Đã triển khai evidence/audit, API/UI admin, conflict và thu hồi có revision. Xem [biên bản nghiệm thu](../../docs/tickets-17-20-21-verification.md). Các mục bên dưới về ngưỡng “chưa chốt” phản ánh thời điểm 2026-09-07; đo chất lượng thực và hiệu chỉnh sau v1 vẫn chưa hoàn tất.

## Thay đổi so với trước

Trước: mọi nghĩa mới phải được admin duyệt thủ công trước khi dùng cho văn bản khác.
Nay: người dùng vẫn nhận kết quả AI ngay trong phiên; hệ thống tích lũy bằng chứng
để tự cho phép tái sử dụng theo ngữ cảnh. Admin tập trung vào ngoại lệ và kiểm tra mẫu.

## Các mức và chuyển trạng thái

1. **Ứng viên:** lưu nghĩa, nguồn/model/phiên bản chính sách, bằng chứng ngữ cảnh tối
   thiểu, thời điểm và độ tin cậy. Chưa tái sử dụng cho văn bản khác.
2. **Dùng có điều kiện:** tự nâng mức khi đủ bằng chứng độc lập nhất quán, vượt các
   kiểm tra hợp lệ và không có xung đột chưa xử lý. Chỉ dùng trong ngữ cảnh tương tự;
   không đưa thành phép thay thế toàn cục hoặc nghĩa đứng đầu danh sách mặc định.
3. **Đã xác nhận:** admin xác nhận hoặc hệ thống tự nâng mức theo tiêu chí được hiệu
   chỉnh bằng đánh giá chất lượng. Nghĩa vẫn phụ thuộc ngữ cảnh, có nguồn và phiên bản.
4. **Cần xem xét / đã thu hồi:** có xung đột, phản hồi sai hoặc bị admin thu hồi thì
   ngừng tái sử dụng phần liên quan, chuyển ngoại lệ cho admin, giữ audit.

Giai đoạn đầu triển khai mức dùng có điều kiện. Chỉ bật tự nâng lên đã xác nhận sau
khi đo chất lượng; việc chốt chính sách không có nghĩa ngưỡng đã được kiểm chứng.

## Điều kiện bằng chứng

- Confidence AI không đủ để tự duyệt. Xét nhiều ngữ cảnh độc lập, tính nhất quán,
  xung đột và kết quả kiểm tra. Số lần lặp một câu không phải nhiều bằng chứng.
- Request trùng, cache-hit, retry, nội dung sao chép và kết quả phát sinh do tái sử
  dụng chính nghĩa đó không được tự củng cố số bằng chứng. Có kiểm soát thao túng
  bằng gửi lặp; không coi nhiều tài khoản mặc nhiên là nguồn độc lập.
- Những nghĩa khác nhau trong ngữ cảnh khác nhau có thể cùng tồn tại (`dc` là
  `được` hoặc `địa chỉ`). Xung đột cần xem xét là nghĩa cạnh tranh trong cùng phạm vi.
- Ngưỡng số bằng chứng, cách xác định ngữ cảnh tương tự, cửa sổ thời gian, tỷ lệ
  kiểm tra mẫu và điều kiện nâng/hạ mức phải có phiên bản và được đo; chưa chốt số.
- Chỉ lưu dữ liệu trong phạm vi được phép; admin xem ngữ cảnh tối thiểu, không
  được cấp quyền đọc toàn lịch sử riêng. Không biến nghĩa thành override riêng user.

## Quản trị và tính nhất quán

Admin có hàng chờ ưu tiên xung đột, phản hồi sai và mức ảnh hưởng; hỗ trợ thao tác
theo nhóm, sửa/thu hồi và audit từng mục. Có kiểm tra mẫu định kỳ cho nghĩa được
tự động cho dùng; lịch/tỷ lệ mẫu được cấu hình khi triển khai, chưa tạo automation.

Thu hồi phải ngăn dùng lại ở request tiếp theo, invalidation cache liên quan và
ngăn bootstrap/đếm bằng chứng cũ tự phục hồi nghĩa. Response đang chạy cũng phải
kiểm tra phiên bản hiệu lực trước khi áp dụng. Lịch sử giữ phiên bản đã sử dụng,
không âm thầm viết lại output cũ. Lưu bằng chứng thất bại không làm hỏng kết quả
chuẩn hóa hiện tại nhưng phải có tín hiệu để vận hành phát hiện.

## Nghiệm thu khi triển khai ticket 17

- [ ] Chuẩn hóa hiện tại không đợi admin; tạo ứng viên có nguồn và ngữ cảnh tối thiểu.
- [ ] Bằng chứng độc lập đủ điều kiện tự nâng mức; cache/retry/copy/reuse không tăng điểm.
- [ ] Nghĩa được tái sử dụng chỉ trong ngữ cảnh phù hợp; đa nghĩa không bị ép thành một.
- [ ] Xung đột bị chặn tái sử dụng và xuất hiện trong hàng chờ ngoại lệ.
- [ ] Admin thao tác nhóm, thu hồi và xem audit; API thực thi quyền admin.
- [ ] Thu hồi có hiệu lực với cache/request đang chạy, không hồi sinh từ bootstrap.
- [ ] Dataset-only và nhãn nguồn AI có chính sách rõ: không âm thầm coi ứng viên
  dùng có điều kiện là dataset đã xác nhận hoặc phát sinh inference khi không cho phép.
- [ ] Kiểm tra mẫu và phép đo sửa đúng/sai xác định ngưỡng trước khi bật tự xác nhận.
- [ ] Đánh giá dữ liệu được phép, tải/lưu trữ và khả năng thao túng trước triển khai thực tế.

Liên quan: ticket 17 chủ trì; 05/06/08 về nguồn và truy vết; 11 về dataset-only;
12/14 về ngân sách/điều phối; 18/19 về hiệu lực, thu hồi và cache.
