# Thay đổi mục tiêu teencode — 2026-09-07

Authority: yêu cầu trực tiếp của chủ project trong cuộc trao đổi sau ticket 13.
Review status: đã cập nhật mục tiêu và có implementation/bằng chứng giới hạn; chưa nghiệm thu tổng thể.

## Lý do và thay đổi so với ban đầu

Người dùng có thể chỉ là người đọc, không biết nghĩa gốc. Công cụ phải chủ động
giúp giải nghĩa, không chuyển trách nhiệm này sang người dùng.

| Nội dung | Ban đầu | Hiện hành |
|---|---|---|
| Teencode thiếu ngữ cảnh/confidence thấp | Giữ nguyên | AI chọn nghĩa hợp lý nhất theo ngữ cảnh và cách dùng phổ biến, áp dụng với nhãn suy đoán |
| Không có nghĩa trong dataset | Giữ bất định khi thiếu căn cứ | AI được đề xuất nghĩa ngoài dataset cho văn bản hiện tại |
| Confidence | Ngưỡng chặn mọi sửa đổi | Không dùng riêng ngưỡng để loại đề xuất teencode hợp lệ; không trình bày như độ chính xác |
| AI không chạy/lỗi/quota/dataset-only | Giữ phần chưa rõ | Giữ nguyên chính sách fallback, không tự lấy nghĩa đầu danh sách |
| Không tìm được nghĩa hợp lý | Giữ nguyên | Vẫn có thể giữ nguyên; không cam kết giải mã mọi chuỗi |
| Dùng chung nghĩa mới | Admin duyệt mọi nghĩa | Tự cho dùng có điều kiện theo bằng chứng/ngữ cảnh; admin xử lý ngoại lệ và kiểm tra mẫu — [chính sách đã chốt](shared-meaning-policy.md) |
| Provider | Kimi K3 | NVIDIA Nemotron 3.5 Lightning theo yêu cầu đổi model |

Quyết định này thay phần yêu cầu giữ nguyên bất định cho **teencode có đề xuất AI
hợp lệ**, không cho phép viết lại sáng tạo, bịa sự kiện, đổi số/URL/mã, bỏ định dạng,
hoặc tự suy đoán dấu câu và lỗi chính tả ngoài phạm vi ticket tương ứng.

## Đã thực hiện và đã kiểm chứng

- Prompt yêu cầu tự giải nghĩa; verifier cho phép đề xuất teencode có confidence
  hợp lệ lớn hơn 0 dưới ngưỡng, sau kiểm tra literal/whitespace; live service áp
  dụng kết quả và giữ trạng thái `uncertain`, lý do `ai_inferred_meaning` khi phù hợp.
- Cache giữ kết quả và trạng thái; không bắt người dùng chọn nghĩa; UI giải thích
  nghĩa suy đoán có thể không đúng ý tác giả. Đây là thông báo mức kết quả, chưa
  chứng minh truy vết mức từng từ trong mọi trường hợp nhiều đoạn.
- Test tái hiện trước sửa: `dk học phần` bị giữ nguyên dù AI đề xuất `đăng ký học phần`
  với confidence 0.55. Sau sửa, test verifier/cache và live service thật với fake
  provider đạt; test phản hồi xóa URL vẫn bị loại đạt.
- Backend toàn bộ: 457 passed, 1 skipped, 39 subtests tại lần chạy trước khi thêm
  test bảo vệ URL cuối; sau đó nhóm verifier/live có 58 tests đạt. Không cộng hai
  lần chạy thành một báo cáo toàn suite mới. Frontend 10 tests đạt; Ruff/Mypy đạt.
- Smoke Nemotron thật: `hôm nay dk học phần` → `Hôm nay đăng ký học phần`, 6.871 giây,
  một đoạn được kiểm tra, `verified/provider_checked`. Một câu không phải benchmark.
- Local `.env` đã bật `AI_DISABLE_NETWORK=0`; process đang chạy cần tải lại cấu hình.
  Consent trên UI và ngân sách vẫn có hiệu lực. Không suy đây là quyền production.

## Checklist bắt buộc khi review tổng thể

- [ ] Teencode ngoài dataset thực sự được nhận diện và đi vào AI: đo bỏ sót, gồm câu
  ngắn, chuỗi lạ, teencode lẫn số; không nhận nhầm tên/ngoại ngữ/mã là viết tắt.
- [ ] Ngữ cảnh rõ, thiếu ngữ cảnh, nghĩa phổ biến và nghĩa trái dataset: đánh giá
  sửa đúng/sai và biến đổi ý; không lấy số từ đã sửa hoặc confidence làm chất lượng.
- [ ] Đề xuất confidence thấp hiển thị/copy/lưu đúng output và nhãn suy đoán, kể cả
  cache-hit, response muộn, reload lịch sử; không bị đổi thành “đã chắc chắn”.
- [ ] Văn bản nhiều đoạn trộn đoạn chắc chắn, suy đoán và timeout/quota: giữ được
  phần đã làm, phạm vi còn thiếu và bất định; không bị mất nhãn do tổng hợp chunk.
- [ ] Highlight hai phía truy vết đúng nghĩa do AI suy ra, gồm từ lặp và sửa nhiều loại.
- [ ] Không có AI/consent/budget hoặc phản hồi sai cấu trúc: fallback đúng, không
  ghi đề xuất bị từ chối vào output/cache; URL/mã/định dạng/phủ định được bảo toàn.
- [ ] Nghĩa dùng chung đi qua tích lũy bằng chứng độc lập và điều kiện ngữ cảnh; chống đếm trùng/tự củng cố, có ngoại lệ và thu hồi theo [chính sách mới](shared-meaning-policy.md). Ticket 17 chưa được đóng bởi việc chốt chính sách.
- [ ] Đo chất lượng/latency/quota Nemotron trên bộ dữ liệu đại diện được phép; chưa
  có cam kết bao phủ 100%, SLA hoặc nghiệm thu production.

Các checkbox này là phần còn phải review, không phủ nhận các test cụ thể đã đạt.
Trạng thái triage và hoàn thành của các ticket khác không tự thay đổi theo tài liệu này.
