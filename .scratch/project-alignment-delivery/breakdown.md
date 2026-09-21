# Breakdown đề xuất — đưa project về specification

> Mục tiêu hiện hành cập nhật 2026-09-07: [chủ động giải nghĩa teencode, thay đổi so với ban đầu và checklist review tổng thể](teencode-policy-change.md). Chính sách này thay phần “confidence thấp thì giữ nguyên” đối với đề xuất teencode hợp lệ. Các kết quả nghiệm thu cũ chỉ chứng minh phạm vi đã ghi, không tự đóng các kiểm tra mới.

Status: needs-triage
Publication: draft — chưa xuất bản implementation tickets
Date: 2026-09-06

Nguồn: [specification](../project-fit-wayfinding/spec.md), [bản đồ điều tra](../project-fit-wayfinding/map.md). Chỉ tạo artifact lập kế hoạch; không thay code, cấu hình, dữ liệu, spec hoặc issue cha.

## Ticket 18 hoàn tất — 2026-09-08

[Ticket 18](drafts/18-dictionary-consistency.md) đã triển khai và nghiệm thu theo topology một host/consumer được chủ project xác nhận. [Bằng chứng](ticket-18-evidence.md): hai worker, ba phiên trình duyệt, export lỗi/repair và bảo vệ seed. Thứ tự tiếp theo vẫn **19 → 17 → 20 → 21**, kiểm tra blocker riêng từng ticket; chưa đánh dấu các ticket đó hoàn tất.

## Các lát cắt đề xuất

### Ticket 13 hoàn tất nội bộ — 2026-09-07

Chủ project đã thay Kimi bằng `nvidia/nemotron-3.5-lightning-30b-a3b`. Tích hợp và smoke backend thật đã đạt: 13.119 giây, `verified/provider_checked`, `hôm nay dk học phần` → `Hôm nay đăng ký học phần`. Đã sửa payload HTTP 400 và đặt reasoning budget 256. Xem [ticket 13](drafts/13-kimi-integration.md) và [bằng chứng](nemotron-13-evidence.md). Các ghi chú “chưa bắt đầu/không gọi inference” và blocker Kimi bên dưới là lịch sử đã được yêu cầu mới thay thế cho scope nội bộ này; không bao gồm production hoặc đánh giá chất lượng diện rộng.

### Cập nhật thực hiện theo yêu cầu mới của chủ project

Đã triển khai chuỗi 12 → 14 → 15 → 16 bằng fake AI sau xác nhận phạm vi một host; xem [bằng chứng thực hiện](execution-evidence.md). Các ghi chú cấm implementation bên dưới thuộc phiên lập kế hoạch trước, được yêu cầu thực hiện mới thay thế cho bốn ticket này. Ticket 13 chưa bắt đầu: disclosure Free Endpoint chưa đóng câu hỏi trial cho công việc thực tế và chưa có hợp đồng Kimi thực tế. Không thay cấu hình/provider sang Kimi hoặc gọi inference thật.

1. **[Chặn truy cập lịch sử riêng của người khác](drafts/01-private-history.md) — P0.** Blocked by: Không. Kết quả: Mỗi tài khoản chỉ xem/xóa lịch sử của chính mình; admin tiếp tục quản lý tài khoản theo quyền sẵn có.

2. **[Đưa user về quyền chỉ xem từ điển và bỏ form hỏi nghĩa](drafts/02-readonly-dictionary.md) — P0.** Blocked by: Không. Kết quả: User xem/tìm từ điển và sử dụng chuẩn hóa mà không có form tạo nghĩa riêng hoặc câu hỏi nghĩa gốc.

3. **[Giữ khoảng cách và ranh giới đoạn qua toàn bộ chuẩn hóa](drafts/03-preserve-format.md) — P0.** Blocked by: Không. Kết quả: Nhập/dán văn bản giữ cấu trúc đoạn và khoảng cách có ý nghĩa sau các bước chuẩn hóa.

4. **[Bảo vệ URL, mã, số và ngoại ngữ đã nhận diện](drafts/04-protect-literals.md) — P0.** Blocked by: Không. Kết quả: Các vùng đã nhận diện cần giữ nguyên không bị viết hoa, thêm dấu hoặc tách khoảng trắng bên trong.

5. **[Hiển thị đúng phạm vi và lý do chưa được AI kiểm tra](drafts/05-truthful-ai-status.md) — P0.** Blocked by: Không. Kết quả: Response và UI phân biệt không cần AI, chưa được kiểm tra, kiểm tra một phần, lỗi/quota và thực sự đã kiểm tra.

6. **[Gắn kết quả và lịch sử với đúng phiên bản đầu vào](drafts/06-versioned-history.md) — P0.** Blocked by: 05. Kết quả: Mỗi kết quả hiển thị/copy/lưu nhận diện được đúng phiên bản input; lịch sử giữ trạng thái một phần nếu có.

7. **[Chủ động giải nghĩa teencode và thể hiện bất định](drafts/07-safe-uncertainty.md) — P0.** Blocked by: 02. Kết quả: AI áp dụng nghĩa teencode hợp lý nhất với nhãn suy đoán khi chưa chắc; không có đề xuất hợp lệ thì giữ nguyên; user không cần chọn nghĩa.

8. **[Đối chiếu hai ô tương đương với highlight teencode hai phía](drafts/08-compare-teencode.md) — P1.** Blocked by: 03, 04. Kết quả: Một đường hoàn chỉnh từ mở rộng teencode đến highlight gốc/kết quả, hai ô tương đương và copy plain text.

9. **[Giải thích sửa dấu và viết hoa bằng highlight](drafts/09-highlight-diacritics-case.md) — P1.** Blocked by: 08. Kết quả: Highlight sửa dấu/chính tả đã có và viết hoa trên hai phía, bao gồm một thay đổi nhiều loại.

10. **[Hiển thị phần emoji bị xóa và thay đổi khoảng trắng](drafts/10-highlight-deletions-spacing.md) — P1.** Blocked by: 08. Kết quả: Đối chiếu được emoji/emoticon bị xóa và các thay đổi whitespace thực sự phát sinh.

11. **[Cho phép dataset-only và thông báo trước khi gửi AI](drafts/11-dataset-only-choice.md) — P0.** Blocked by: 05. Kết quả: User chọn không gửi AI vẫn chuẩn hóa bằng dataset; lựa chọn có hiệu lực ở backend, trạng thái nói rõ giới hạn.

12. **[Áp dụng ngân sách AI chung và giới hạn theo user](drafts/12-shared-ai-budget.md) — P1.** Blocked by: 05, Xác minh môi trường và dữ liệu vận hành. Kết quả: Mọi lần gọi AI đi qua ngân sách tổng và theo user phù hợp môi trường được xác minh.

13. **[Nối Kimi K3 vào một lượt chuẩn hóa có kiểm soát](drafts/13-kimi-integration.md) — P1.** Blocked by: 11, 12, Chốt phạm vi hosted trial, Xác minh hợp đồng Kimi trên tài khoản thực tế. Kết quả: Một lượt chuẩn hóa ngắn được Kimi xử lý trong phạm vi tài khoản đã xác minh, có fallback và trạng thái đúng.

14. **[Tự gọi AI cho phần khó sau dataset, kể cả câu ngắn](drafts/14-automatic-ai-routing.md) — P1.** Blocked by: 07, 11, 12. Kết quả: Luồng chính tự gọi AI khi được phép, áp dụng đề xuất teencode hợp lệ kể cả confidence thấp với nhãn suy đoán; còn phải đo bỏ sót bộ nhận diện.

15. **[Trả kết quả dataset sớm và cập nhật AI sau khoảng nghỉ gõ](drafts/15-progressive-typing.md) — P1.** Blocked by: 06, 14. Kết quả: User thấy phần dataset trước, AI cập nhật đúng phiên sau khoảng nghỉ hoặc ranh giới câu; copy được trạng thái đang có.

16. **[Xử lý văn bản dài theo ngữ cảnh xuyên đoạn](drafts/16-document-context.md) — P1.** Blocked by: 03, 15. Kết quả: Dán văn bản dài tự xử lý từng phần với ngữ cảnh liên quan, giữ đoạn và minh bạch phần chưa kiểm tra.

17. **[Tích lũy bằng chứng và tự tái sử dụng nghĩa AI theo ngữ cảnh](drafts/17-ai-meaning-candidates.md) — P1.** Blocked by: 14, Xác minh môi trường và dữ liệu vận hành, Chốt phạm vi hosted trial. Kết quả: AI xử lý ngay trong phiên; tự tích lũy bằng chứng và cho dùng nghĩa theo ngữ cảnh, admin xử lý ngoại lệ/kiểm tra mẫu. [Chính sách và tiêu chí](shared-meaning-policy.md); chưa triển khai cơ chế này.

18. **[Áp dụng cập nhật từ điển nhất quán sau khi admin lưu](drafts/18-dictionary-consistency.md) — P1.** Blocked by: Xác minh môi trường và dữ liệu vận hành, Kiểm kê consumer ngoài repository. Kết quả: Sau lưu, lần chuẩn hóa tiếp theo dùng dữ liệu hiệu lực; lỗi đồng bộ có trạng thái rõ và có thể xác định kết quả.

19. **[Cho admin xóa mục viết tắt khỏi từ điển hiệu lực](drafts/19-delete-dictionary-entry.md) — P1.** Blocked by: 18. Kết quả: Admin xóa/ngừng hiệu lực một mục, user không còn thấy hoặc bị áp dụng mục đó ở lần chuẩn hóa tiếp theo.

20. **[Sửa lỗi chính tả có căn cứ và giải thích thay đổi](drafts/20-contextual-spelling.md) — P1.** Blocked by: 04, 07, 09, 14. Kết quả: Các lỗi chính tả trong bộ ví dụ có căn cứ được sửa và highlight; trường hợp chưa chắc giữ nguyên.

21. **[Bổ sung dấu câu có căn cứ và highlight phần được thêm](drafts/21-contextual-punctuation.md) — P1.** Blocked by: 04, 08, 14. Kết quả: Dấu câu chỉ được thêm khi có cơ sở ngữ cảnh; UI giải thích phần thêm mà không đổi văn phong.

22. **[Điều tra hợp đồng Kimi trên tài khoản thực tế](drafts/wayfinding-10-kimi-account-contract.md).** Blocked by: phạm vi hosted trial. Kết quả: bằng chứng đủ để chọn request/response/quota thực tế; không triển khai adapter. Dự kiến nối vào nhóm wayfinding hiện có bằng số 10.

## UNCERTAIN — tiếp tục ticket đã tồn tại

Không tạo bản sao của các điều tra sau:

- [Xác minh môi trường và dữ liệu vận hành](../project-fit-wayfinding/issues/04-runtime-data.md).
- [Chốt bằng chứng nghiệm thu](../project-fit-wayfinding/issues/05-acceptance-evidence.md).
- [Chốt phạm vi quản lý tài khoản](../project-fit-wayfinding/issues/06-admin-scope.md).
- [Chốt phạm vi hosted trial](../project-fit-wayfinding/issues/08-trial-boundary.md).
- [Kiểm kê consumer ngoài repository](../project-fit-wayfinding/issues/09-external-consumers.md).

Chất lượng Kimi và hiệu năng thật vẫn cần đợt đo riêng theo ticket bằng chứng nghiệm thu, sau khi có điều kiện và integration phù hợp; test giả lập không đóng điểm chưa chắc chắn này. Chưa tạo ticket mở rộng account administration hoặc thay retention/backup vì quyết định còn mở.

## Thứ tự triển khai đề xuất

1. Phiên tiếp theo bắt đầu **01 — Chặn truy cập lịch sử riêng của người khác**: scope nhỏ, không blocker, chứng minh UI và quyền API. Hoàn thành một ticket trước khi lấy ticket tiếp.
2. Tiếp theo **03 → 04 → 05 → 02 → 07 → 06 → 11**: bảo toàn văn bản, trạng thái trung thực, tự động không hỏi nghĩa, phiên bản và lựa chọn gửi AI.
3. Nhánh đối chiếu độc lập **08 → 09 → 10**; không cần đợi Kimi thật.
4. Giải quyết điều tra runtime, consumer ngoài và trial. Khi đủ bằng chứng: **12 → 14 → 15 → 16**; **13** chỉ bắt đầu khi điều tra Kimi và trial đã xong. Các ticket dùng fake AI không bị chặn bởi chất lượng model thật.
5. Sau blocker tương ứng: **18 → 19**, **17**, **20**, **21**. Đây là thứ tự mặc định; có thể lấy nhánh không bị chặn để tránh đợi thông tin.
6. Đánh giá Kimi thật/chất lượng/tải theo bằng chứng nghiệm thu đã chốt trước khi kết luận sẵn sàng pilot. Không có ticket triển khai production tự động.

P0 là rủi ro trực tiếp đối với nghĩa, quyền hoặc kết quả người dùng; P1 bổ sung capability. Priority không thay dependency. Mọi issue được xuất bản sau duyệt vẫn chưa được phép triển khai trong phiên hiện tại.

## Phạm vi được giữ

Không tạo ticket xây lại stack, auth/session, copy cơ bản, ownership đã đúng, phrase dữ liệu đang dùng, seed không ghi đè hay công cụ build/eval hữu ích. Regression trong ticket mới chỉ bảo vệ các hành vi đó. Không tạo refactor lớn, xóa bảng/endpoint chưa biết consumer hoặc thêm dashboard chỉ vì schema có sẵn.

## Cần duyệt

Xác nhận độ nhỏ/lớn của 21 lát cắt, các dependency và có cần gộp/tách mục nào trước khi xuất bản mỗi ticket vào issues/. Điều tra hiện có giữ nguyên.
