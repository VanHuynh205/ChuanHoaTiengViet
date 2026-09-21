# Specification — Chuẩn hóa văn bản tiếng Việt theo ngữ cảnh

Status: ready-for-agent
Version: 1.2 — cập nhật tự tái sử dụng nghĩa theo bằng chứng 2026-09-07
Date: 2026-09-06
Scope: Trạng thái mong muốn của sản phẩm; không phải mô tả hệ thống đang chạy.
Authority: Mục đích ban đầu, Q1–Q16 đã được đồng ý, lựa chọn Kimi K3 thay Gemini, và kết luận review/điều tra đã có bằng chứng.
Execution authorization: Tài liệu này không cấp quyền triển khai, gọi inference, thay cấu hình, migration, xóa dữ liệu hoặc tạo implementation ticket.
Readiness: Hợp đồng hành vi cốt lõi đã xác định; các điều kiện mở trong Further Notes không được tự coi là đã chốt. Nhãn tracker theo quy trình to-spec không phải xác nhận sẵn sàng production.

> Cập nhật v1.2: [chính sách dùng chung nghĩa AI](../project-alignment-delivery/shared-meaning-policy.md) thay yêu cầu mọi nghĩa phải chờ admin. Tự dùng có điều kiện theo ngữ cảnh/bằng chứng; admin xử lý ngoại lệ, thu hồi và kiểm tra mẫu. Chính sách đã chốt, cơ chế chưa triển khai.

## Problem Statement

> Thay đổi được chủ project yêu cầu ngày 2026-09-07: AI chủ động giải nghĩa teencode, kể cả ngoài dataset hoặc confidence thấp, và áp dụng với nhãn suy đoán. [Hồ sơ thay đổi so với v1.0 và checklist review](../project-alignment-delivery/teencode-policy-change.md) có hiệu lực cao hơn các mô tả giữ nguyên bất định cũ trong tài liệu này, riêng cho đề xuất teencode hợp lệ. Provider hiện là NVIDIA Nemotron; các ghi chú Kimi còn lại là lịch sử điều tra, không phải bằng chứng Nemotron hoặc quyền production.

Người đọc đánh giá sản phẩm, tin nhắn và bài đăng tiếng Việt gặp văn bản chứa teencode, viết tắt nhiều nghĩa, thiếu dấu, sai chính tả, emoji, emoticon và dấu câu thiếu hoặc không phù hợp. Người nhập văn bản vào công cụ có thể không phải tác giả, nên không thể chịu trách nhiệm giải thích những từ chưa biết.

Nhóm ưu tiên là chuyên viên làm sạch và phân tích đánh giá khách hàng. Họ cần văn bản dễ đọc nhưng vẫn giữ đúng ý, giọng điệu, cảm xúc, số liệu, tên riêng và ngoại ngữ để không làm sai kết quả phân tích. Người dùng phổ thông cũng cần cùng khả năng đọc hiểu và đối chiếu.

Các kết quả mong muốn là chuẩn hóa tự động theo ngữ cảnh, tốc độ phù hợp thao tác nhập/dán, sử dụng AI trong ngân sách, nhìn được từng thay đổi, copy kết quả và quản lý lịch sử riêng. Việc sửa từ điển dùng chung và quản lý tài khoản thuộc quyền admin.

Có AI, nhiều test pass hoặc một kết quả được model tự đánh giá confidence cao chưa chứng minh văn bản đúng nghĩa. Sản phẩm phải thể hiện trung thực phần đã xử lý, phần chưa chắc chắn và phần chưa được AI kiểm tra.

## Solution

### Mục tiêu và thứ tự ưu tiên

- G-01: Bảo toàn ý nghĩa, giọng điệu và mức độ cảm xúc; không viết lại theo ý phỏng đoán hoặc biến văn bản thành văn phong khác.
- G-02: Tự động thực hiện quy trình chuẩn hóa, không yêu cầu người dùng cung cấp nghĩa gốc hay chọn nghĩa để quy trình hoàn tất.
- G-03: Chuẩn hóa bằng dữ liệu đã được duyệt và quy tắc trước; sau đó tự đánh giá nhu cầu dùng AI theo ngữ cảnh.
- G-04: Thứ tự ưu tiên khi xung đột: bảo toàn nghĩa → tuân thủ ngân sách → tốc độ. Không tự chuyển sang API trả phí.
- G-05: Với teencode, AI chủ động chọn nghĩa hợp lý nhất và áp dụng kể cả confidence thấp, kèm nhãn suy đoán. Giữ nguyên khi AI không chạy/lỗi hoặc không có cách giải nghĩa hợp lý; không cam kết sửa mọi chuỗi.
- G-06: Mỗi kết quả phải có thể đối chiếu với đúng đầu vào và giải thích thay đổi.
- G-07: Phân quyền tại hệ thống, không chỉ ẩn nút trên giao diện.

### Thuật ngữ sử dụng trong specification

| Thuật ngữ | Nghĩa |
|---|---|
| Văn bản gốc | Nội dung người dùng nhập/dán, được giữ để đối chiếu; không bị pipeline ghi đè. |
| Phiên bản đầu vào | Một trạng thái cụ thể của văn bản gốc trong quá trình người dùng chỉnh sửa. |
| Phiên chuẩn hóa | Lần xử lý một đầu vào với kết quả, thay đổi, trạng thái và dữ liệu liên quan nhất quán. |
| Thay đổi chuẩn hóa | Phép thay, thêm hoặc xóa nội dung có vị trí ở bản gốc/kết quả và loại thay đổi. |
| Vùng được bảo vệ | Nội dung cần giữ nguyên như ngoại ngữ, URL, email, mã, số hoặc tên riêng đã nhận diện đủ chắc chắn. |
| Phần bất định | Từ/cụm chưa đủ ngữ cảnh để chọn nghĩa hay sửa một cách đáng tin cậy. |
| Nghĩa đã duyệt | Nghĩa được admin cho phép dùng trong từ điển chung; không đồng nghĩa luôn đúng trong mọi ngữ cảnh. |
| Ứng viên nghĩa mới | Đề xuất do AI phát hiện, kèm bằng chứng ngữ cảnh phù hợp để admin xem xét; chưa được xuất bản dùng chung. |
| Kết quả một phần | Kết quả hiện có trong khi còn xử lý hoặc thiếu một phần kiểm tra cần thiết. |
| Dataset | Tập dữ liệu và quy tắc chuẩn hóa đang có hiệu lực, bao gồm nghĩa/cụm đã duyệt và dữ liệu hỗ trợ ngôn ngữ. |
| User | Người có quyền sử dụng dịch vụ và đọc dữ liệu được phép; không sửa từ điển chung hoặc nghĩa riêng. |
| Admin | Người quản lý từ điển/ứng viên và tài khoản theo phạm vi quyền đã chốt; không mặc định được đọc lịch sử riêng của user. |

Các thuật ngữ này mô tả hợp đồng sản phẩm, không bắt buộc tạo class, bảng hoặc dịch vụ riêng cho mỗi thuật ngữ.

### Hai luồng sử dụng

**Nhập tay**

1. User nhập/chỉnh sửa ở ô đầu vào; ô gốc giữ nguyên nội dung họ nhập.
2. Hệ thống cập nhật sớm phần chuẩn hóa chắc chắn bằng dataset, có trì hoãn ngắn thích hợp để tránh xử lý từng sự kiện bàn phím không cần thiết.
3. Sau khoảng nghỉ gõ hoặc ranh giới câu, hệ thống đánh giá nhu cầu AI. Dấu câu kết thúc không phải điều kiện bắt buộc duy nhất.
4. Khi có ngữ cảnh mới, được phép sửa lại kết quả, ưu tiên câu đang nhập và phần trước thực sự liên quan.
5. Kết quả của phiên bản cũ không được ghi đè phiên bản mới hoặc được lưu như kết quả của đầu vào mới.

**Dán văn bản**

1. User dán một văn bản từ ngắn đến khoảng 5.000 từ; hệ thống tự bắt đầu xử lý.
2. Trả kết quả chắc chắn sớm và hiển thị tiến độ; cập nhật từng phần khi xử lý tiếp.
3. Xét ngữ cảnh trong đoạn hoặc xuyên đoạn/toàn văn khi liên quan. Chia nhỏ để xử lý không được làm mất ngữ cảnh cần thiết hoặc ranh giới đoạn.
4. User có thể copy kết quả đang có; giao diện phải nói rõ nếu kết quả còn đang xử lý hoặc thiếu kiểm tra AI cần thiết.

Mốc 5.000 từ là phạm vi nghiệm thu mục tiêu, không phải số đo hiệu năng hiện tại. Giới hạn thực tế phải công khai; không cắt văn bản hoặc đầu ra âm thầm.

### Hợp đồng chuẩn hóa

- N-01: Mở rộng teencode/viết tắt theo nghĩa phù hợp ngữ cảnh. Một từ có thể có nhiều nghĩa; thứ tự lưu trong danh sách không phải bằng chứng chọn nghĩa.
- N-02: Khôi phục/sửa dấu và lỗi chính tả khi có cơ sở. Một từ không nằm trong dataset không tự động là lỗi.
- N-03: Không tự thêm thông tin, đảo phủ định, đổi chủ thể, số liệu hoặc mức độ đánh giá để làm câu “tự nhiên hơn”.
- N-04: Xóa emoji/emoticon theo phạm vi đã chốt, bao gồm biểu tượng như :)); vẫn giữ bản gốc để người dùng thấy sắc thái đã bị loại bỏ. Không suy rằng xóa emoji bảo toàn được mọi sắc thái.
- N-05: Chỉ xóa ký tự rác khi nhận diện đủ chắc chắn. Không xóa mọi “ký tự đặc biệt”: C++, C#, 9/10, 50%, URL, email và mã có ý nghĩa phải được bảo toàn.
- N-06: Viết hoa đầu câu và tên riêng khi có cơ sở. Xuống dòng do hiển thị không tạo câu mới; ranh giới chunk không tạo viết hoa mới. Không viết hoa các thành phần trong URL/email/mã hoặc tự hạ chữ hoa của tên riêng.
- N-07: Bổ sung dấu câu khi ngữ cảnh đủ rõ; không tự thêm ? hoặc ! để phóng đại hoặc suy đoán ý định. Nếu thiếu căn cứ thì giữ nguyên.
- N-08: Giữ nguyên ngoại ngữ, tên sản phẩm, mã và biểu thức số phù hợp trong ngữ cảnh. Không dùng danh sách từ tiếng Việt như bằng chứng duy nhất để sửa từ trùng hình thức với ngoại ngữ.
- N-09: Không làm dính từ, chèn khoảng trắng sai vào số/URL/mã, hoặc gộp đoạn khi xóa emoji và ghép kết quả.
- N-10: Với teencode bất định, AI dùng ngữ cảnh và cách dùng phổ biến để đề xuất nghĩa, kể cả ngoài dataset; đề xuất hợp lệ được áp dụng với trạng thái bất định trung thực. Chỉ giữ nguyên khi không có đề xuất hợp lệ; user không phải cung cấp nghĩa.
- N-11: AI được kiểm tra cả các sửa đổi dataset có dấu hiệu sai ngữ cảnh; không chỉ xử lý từ hoàn toàn mới.
- N-12: AI không khả dụng không hợp thức hóa một nghĩa dataset đã đoán. Fallback chỉ giữ các thay đổi có cơ sở và giữ nguyên phần còn bất định.
- N-13: Văn bản đầu vào là dữ liệu cần chuẩn hóa, kể cả khi chứa câu ra lệnh; nội dung đó không được thay đổi chính sách chuẩn hóa hoặc quyền hệ thống.

### Kết quả, trạng thái và đối chiếu

- R-01: Hai ô có cách trình bày tương đương về chữ, xuống dòng và kích thước sử dụng; cạnh nhau trên màn hình rộng, vẫn dùng được trên màn hình hẹp. Không bắt buộc cùng phần tử DOM hoặc cùng quyền chỉnh sửa.
- R-02: Hiển thị thay đổi ở bản gốc và kết quả theo sáu nhóm: teencode; dấu/chính tả; viết hoa; dấu câu; phần bị xóa; khoảng trắng.
- R-03: Mỗi nhóm có màu phân biệt và giải thích không chỉ dựa vào màu. Màu cụ thể chưa được chốt.
- R-04: Thay đổi có nhiều loại dùng một màu chính nhưng khi chọn phải xem được đầy đủ các loại liên quan; thứ tự ưu tiên màu là chi tiết thiết kế, không được làm mất thông tin.
- R-05: Phần bị xóa phải truy vết được ở bản gốc; phần được thêm phải có điểm đối chiếu. Từ lặp phải đánh dấu đúng lần xuất hiện.
- R-06: Bất định có dấu hiệu riêng, không hiển thị như một sửa đổi chắc chắn hoặc yêu cầu user trả lời nghĩa.
- R-07: Trạng thái phải phân biệt đang xử lý, hoàn tất xử lý, còn bất định và chưa kiểm tra AI đầy đủ. Những trạng thái này có thể cùng tồn tại ở các phạm vi khác nhau.
- R-08: Không gọi AI vì không cần phải khác với không gọi được vì chưa đồng ý, quota, lỗi hoặc provider chưa sẵn sàng.
- R-09: “AI đã kiểm tra” chỉ áp dụng cho phần thực sự được kiểm tra hoặc tái sử dụng kết quả kiểm tra tương thích. Chạy 0 chunk không được trở thành “toàn văn AI verified”.
- R-10: Không trình bày confidence tự báo của model như xác suất chính xác đã được kiểm định.
- R-11: Copy trả văn bản thuần đúng phiên bản đang hiển thị, không kèm markup highlight. Trạng thái một phần được thể hiện rõ trước thao tác, không tự chèn lời giải thích vào văn bản gốc/kết quả.
- R-12: Lỗi AI không làm mất văn bản đã nhập và kết quả chắc chắn đang có.

### Từ điển và học nghĩa

- D-01: User được xem/tìm nghĩa trong từ điển, bao gồm nhiều nghĩa và phạm vi ngữ cảnh có sẵn.
- D-02: Chỉ admin thêm, sửa, xóa mục từ điển chung và quản lý cụm từ đã duyệt. Cách xóa vật lý hay ngừng hiệu lực là chi tiết implementation chưa được chọn.
- D-03: AI tự động ghi nhận nghĩa mới phù hợp thành ứng viên, khi việc lưu/dùng dữ liệu được phép, kèm ngữ cảnh tối thiểu cần thiết, nguồn và trạng thái duyệt.
- D-04: Hệ thống tự cho tái sử dụng nghĩa có điều kiện theo bằng chứng độc lập và ngữ cảnh; admin xem ngoại lệ, duyệt theo nhóm, sửa/thu hồi và kiểm tra mẫu. Không đọc toàn lịch sử riêng để duyệt.
- D-05: Nghĩa mới hợp lý do AI suy ra có thể dùng cho văn bản hiện tại, kể cả dưới ngưỡng confidence với nhãn suy đoán; được tái sử dụng khi đạt điều kiện bằng chứng/ngữ cảnh hoặc được admin xác nhận, có audit và thu hồi; không tự biến thành nghĩa mặc định toàn cục.
- D-06: Nghĩa đã duyệt không trở thành lựa chọn bắt buộc trong mọi ngữ cảnh; ngữ cảnh khác vẫn có thể tạo bất định hoặc đề xuất khác.
- D-07: Không hỏi user nghĩa gốc, không lưu nghĩa riêng cho user và không bắt chọn giữa các phiên bản để hoàn tất.
- D-08: Thay đổi từ điển phải có hiệu lực nhất quán cho những lần chuẩn hóa tiếp theo; cache không được trả vô hạn kết quả dựa trên dữ liệu đã hết hiệu lực.
- D-09: Seed/bootstrap không được âm thầm ghi đè các quyết định admin đã duyệt.
- D-10: Ghi nhận được người thực hiện, nguồn và quyết định moderation. Lỗi thống kê phụ trợ không làm mất kết quả chuẩn hóa.

### Quyền và lịch sử

| Hành vi | User | Admin |
|---|---|---|
| Chuẩn hóa, copy, xem từ điển | Có | Có |
| Xem/xóa lịch sử của chính mình | Có | Có |
| Sửa từ điển chung và duyệt ứng viên | Không | Có |
| Tạo nghĩa riêng | Không | Không có capability này trong phạm vi |
| Xem danh sách/quản lý tài khoản | Không | Có, phạm vi chi tiết còn mở |
| Mặc định đọc/xóa lịch sử riêng của người khác | Không | Không |
| Quản lý cấu hình/key AI của hệ thống | Không | Có trong vai trò quản trị; không bắt buộc có màn hình chỉnh key |

- H-01: Lưu lịch sử các phiên đã có kết quả; không tạo bản ghi cho từng lần gõ.
- H-02: Đầu vào, đầu ra và trạng thái lưu phải thuộc cùng phiên bản xử lý. Không ghép input mới với output cũ khi xóa nội dung, rời trang hoặc request trả muộn.
- H-03: Nếu lưu kết quả một phần, phải giữ trạng thái đó; không chuyển thành kết quả hoàn chỉnh trong lịch sử.
- H-04: User chỉ truy cập được lịch sử của mình ở cả UI và API.
- H-05: Giữ kiểm tra phiên đăng nhập/logout/revoke ở server. Không coi thiếu UI quản lý sessions là lý do bỏ bảo vệ phiên.
- H-06: Các thao tác admin phải được kiểm tra quyền ở hệ thống; không dựa vào tên route, nút bị ẩn hoặc dữ liệu role do client tự gửi.
- H-07: Chính sách retention, backup và phục hồi còn cần chốt/kiểm chứng; không coi con số mặc định của script hiện tại là yêu cầu đã được duyệt.

### AI, ngân sách và dữ liệu gửi đi

- A-01: Provider được chủ project đổi sang `nvidia/nemotron-3.5-lightning-30b-a3b` qua NVIDIA Build. Smoke nội bộ đã đạt theo ticket 13; không suy ra chất lượng diện rộng, quota bảo đảm hoặc quyền production.
- A-02: Key do hệ thống quản lý phía server; user không cần cung cấp API key.
- A-03: Đánh giá nhu cầu AI sau dataset; AI tự chạy khi phù hợp và được phép. Câu ngắn có vấn đề vẫn cần được đánh giá, không bỏ qua chỉ vì dưới ngưỡng ký tự tùy ý.
- A-04: Giới hạn theo user và ngân sách tổng; không để một người tiêu hết quota chung. Cache, tái sử dụng phần không đổi và tránh request trùng phải phục vụ mục tiêu này.
- A-05: Có giới hạn thời gian, token và số lần thử thích hợp; không lặp request vô hạn khi quota cạn. Thông số phải được chọn dựa trên hợp đồng provider và số đo, chưa chốt số cụ thể.
- A-06: Khi quota/lỗi làm thiếu kiểm tra, trả phần chắc chắn cùng trạng thái rõ ràng; không âm thầm đổi provider/model có phí.
- A-07: Có thông báo trước khi gửi AI. Người không đồng ý vẫn dùng dataset-only, với giới hạn chất lượng/phạm vi kiểm tra hiển thị trung thực.
- A-08: Phạm vi dữ liệu đã chốt là văn bản công khai hoặc đã loại bỏ thông tin nhạy cảm. Điều này không tự cấp quyền gửi nội dung chứa dữ liệu cá nhân hoặc nội dung provider không cho phép.
- A-09: Không hứa ẩn danh hoàn hảo, không lưu dữ liệu hoặc không dùng dữ liệu cải thiện mô hình khi chưa có bằng chứng.
- A-10: Chỉ dùng hosted trial trong phạm vi được phép bởi điều khoản áp dụng. Việc pilot là đánh giá nội bộ hay phục vụ công việc thật còn mở; không coi “nhóm nhỏ có đăng nhập” là đủ để giải quyết.
- A-11: Khi bắt đầu code, nhắc chủ project cung cấp đoạn Python gọi API. Không yêu cầu hoặc sử dụng đoạn đó trong bước viết specification.

## User Stories

1. As a chuyên viên phân tích đánh giá khách hàng, I want văn bản dễ đọc nhưng giữ nguyên ý, so that kết quả phân tích không bị sai lệch.
2. As a chuyên viên làm sạch dữ liệu, I want giữ phủ định, số liệu và mức độ cảm xúc, so that dữ liệu chuẩn hóa vẫn trung thực.
3. As a người đọc không phải tác giả, I want hệ thống tự xử lý từ khó, so that tôi không phải giải thích nghĩa mình không biết.
4. As a user, I want nhập tay và thấy kết quả cập nhật sớm, so that tôi so sánh ngay khi đang nhập.
5. As a user, I want giữ nguyên ô gốc, so that tôi không mất nội dung ban đầu.
6. As a user, I want kết quả được xét lại khi có ngữ cảnh mới, so that viết tắt được hiểu đúng hơn.
7. As a user, I want response cũ không ghi đè kết quả mới, so that màn hình luôn tương ứng đầu vào hiện tại.
8. As a user, I want dán văn bản và tự bắt đầu xử lý, so that không cần thao tác chuẩn hóa thủ công.
9. As a user, I want xử lý văn bản ngắn lẫn khoảng 5.000 từ, so that cùng công cụ đáp ứng nhiều độ dài.
10. As a user, I want thấy tiến độ và kết quả từng phần, so that tôi biết hệ thống còn đang làm gì.
11. As a user, I want giữ xuống dòng và cấu trúc đoạn, so that văn bản vẫn dễ đối chiếu.
12. As a user, I want dùng ngữ cảnh từ đoạn khác khi có liên quan, so that cùng viết tắt không bị hiểu tách rời.
13. As a user, I want mở rộng teencode theo ngữ cảnh, so that văn bản trở nên dễ hiểu.
14. As a user, I want khôi phục dấu có căn cứ, so that câu không bị đổi sang nghĩa khác.
15. As a user, I want sửa lỗi chính tả rõ ràng, so that văn bản dễ đọc hơn.
16. As a user, I want giữ ngoại ngữ và tên sản phẩm, so that nội dung không bị Việt hóa sai.
17. As a user, I want giữ URL, email, mã và biểu thức số, so that chúng vẫn dùng được sau chuẩn hóa.
18. As a user, I want viết hoa đúng vị trí, so that không xuất hiện chữ hoa vô nghĩa giữa câu.
19. As a user, I want chỉ thêm dấu câu khi đủ rõ, so that hệ thống không suy đoán cảm xúc của tác giả.
20. As a user, I want xóa emoji/emoticon nhưng xem được phần đã xóa, so that tôi hiểu kết quả đã thay đổi thế nào.
21. As a user, I want không bị mất khoảng cách hoặc dính từ, so that kết quả có thể sử dụng.
22. As a user, I want giữ nguyên phần chưa rõ nghĩa, so that công cụ không đưa ra phỏng đoán như sự thật.
23. As a user, I want bất định có dấu hiệu riêng, so that tôi biết giới hạn của kết quả.
24. As a user, I want hai ô trình bày tương đương, so that dễ so sánh bản gốc và bản chuẩn hóa.
25. As a user, I want dùng giao diện trên màn hình nhỏ, so that việc đối chiếu không bị cản trở.
26. As a user, I want mỗi loại thay đổi có màu và mô tả, so that không phải đoán ý nghĩa màu.
27. As a user, I want chọn một thay đổi để xem các loại sửa liên quan, so that hiểu trường hợp nhiều bước cùng tác động.
28. As a user, I want highlight đúng lần xuất hiện của từ lặp, so that không hiểu nhầm phần nào đã sửa.
29. As a user, I want copy văn bản thuần, so that có thể dán kết quả sang công cụ khác.
30. As a user, I want copy kết quả đang có khi cần, so that không phải chờ toàn bộ, nhưng biết nó còn chưa hoàn tất.
31. As a user, I want biết AI đã kiểm tra phần nào, so that không nhầm kết quả dataset với kiểm tra toàn văn.
32. As a user, I want biết khi quota hoặc provider làm gián đoạn, so that hiểu vì sao còn phần chưa được kiểm tra.
33. As a user, I want sử dụng dataset-only nếu không đồng ý gửi AI, so that vẫn sử dụng được dịch vụ trong phạm vi phù hợp.
34. As a user, I want được thông báo việc gửi dữ liệu ra ngoài, so that có quyết định sử dụng có cơ sở.
35. As a user, I want không phải cấu hình API key, so that dịch vụ dễ sử dụng.
36. As a user, I want xem và tìm từ điển nhiều nghĩa, so that hiểu những từ viết tắt thường gặp.
37. As a user, I want lịch sử chứa đúng input/output cùng phiên, so that có thể tin cậy khi xem lại.
38. As a user, I want chỉ tôi xem được lịch sử riêng theo quyền đã chốt, so that nội dung không bị lộ cho người dùng hoặc admin khác.
39. As a user, I want xóa lịch sử của mình, so that kiểm soát nội dung đã lưu.
40. As a user, I want không có lịch sử cho từng phím gõ, so that danh sách không bị ngập bản ghi tạm.
41. As a admin, I want thêm/sửa/xóa nghĩa dùng chung, so that dữ liệu chuẩn hóa được quản lý có trách nhiệm.
42. As a admin, I want quản lý cụm từ có ảnh hưởng ngữ cảnh, so that sửa được những trường hợp vượt một từ đơn.
43. As a admin, I want AI ghi nhận ứng viên nghĩa mới kèm bằng chứng phù hợp, so that có cơ sở kiểm duyệt.
44. As a admin, I want duyệt hoặc từ chối ứng viên, so that suy luận chưa kiểm chứng không lan truyền cho mọi user.
45. As a admin, I want xem nhiều nghĩa thay vì một nghĩa áp dụng tuyệt đối, so that từ điển phản ánh ngữ cảnh.
46. As a admin, I want thay đổi được áp dụng nhất quán sau khi lưu, so that user không nhận kết quả cũ vô hạn.
47. As a admin, I want biết nguồn và lịch sử quyết định từ điển, so that có thể kiểm tra sai sót.
48. As a admin, I want quản lý tài khoản trong quyền được chốt, so that chỉ người phù hợp sử dụng dịch vụ.
49. As a người vận hành, I want bảo vệ phiên đăng nhập và API ở server, so that client không tự vượt quyền.
50. As a người vận hành, I want giới hạn AI theo user và tổng ngân sách, so that dịch vụ không bị một người chiếm hết quota.
51. As a người vận hành, I want không tự phát sinh phí, so that ngân sách đã thống nhất được tuân thủ.
52. As a người đánh giá, I want đo chất lượng theo các trường hợp thực tế và lỗi làm đổi nghĩa, so that quyết định tiếp tục dựa trên bằng chứng.
53. As a người bảo trì, I want công cụ build/eval dữ liệu nội bộ tiếp tục có ích, so that dữ liệu và chất lượng có thể được kiểm chứng.
54. As a chủ project, I want phân biệt điều đã chốt và điều còn cần xác minh, so that không biến giả định hoặc code cũ thành requirement.

## Implementation Decisions

### Những quyết định đã chốt hoặc cần giữ về hành vi

- Giữ kiến trúc ứng dụng hiện tại làm nền tảng; chưa có quyết định xây lại hoặc thay stack.
- Giữ vai trò dataset, phrase normalization, AI adapter, repository, auth/session và moderation. Hành vi sai bên trong các phần đó không được giữ chỉ vì đã có test.
- Một hợp đồng kết quả nhất quán phải phục vụ cả nhập tay và dán; không để từng đường chuẩn hóa tự định nghĩa ý nghĩa “hoàn tất” hoặc “đã kiểm tra”.
- Kết quả phải gắn với phiên bản đầu vào và có thông tin thay đổi đủ cho đối chiếu hai phía. Không quy định bắt buộc một bảng/class/protocol mới.
- Tách về mặt hành vi việc xử lý văn bản hiện tại với xuất bản nghĩa dùng chung; dùng được suy luận cho một ngữ cảnh không có nghĩa đã được phép cập nhật dataset chung.
- Kiểm tra quyền thực sự tại backend; giữ bảo vệ phiên đăng nhập, logout/revoke và ownership.
- Giữ giới hạn request, cache có giới hạn và xử lý nền không làm một request nặng chặn mọi user. Không chọn cơ chế lưu cache phân tán chỉ vì có thể cần về sau.
- Tái sử dụng cache phải tương thích với văn bản, ngữ cảnh, chính sách và dữ liệu đang có hiệu lực; không làm sai ownership hay trạng thái AI.
- Giữ công cụ build/eval nội bộ, dữ liệu phrase đang dùng và telemetry phụ trợ có ích; telemetry không phải bằng chứng quota còn lại hoặc độ chính xác.
- NVIDIA integration phải được đối chiếu hợp đồng Kimi K3 thực tế, không sao chép nguyên tham số GLM hoặc suy “OpenAI-compatible” nghĩa là mọi tham số đều hợp lệ.
- Không đưa các giới hạn hiện tại như độ dài kích hoạt AI, số chunk, timeout, confidence threshold hoặc trần ký tự thành requirement đã chốt.
- Lưu/ngừng hiệu lực từ điển và đồng bộ dữ liệu phải có kết quả rõ ràng; không báo thất bại toàn bộ sau khi đã ghi thành công mà không thể xác định trạng thái.

### Chưa chọn giải pháp

Specification không chỉ định transport streaming, cấu trúc database mới, cách phân đoạn cụ thể, thuật toán confidence, thư viện editor, khóa cache, cơ chế quota phân tán hay framework mới. Những lựa chọn đó phải được đánh giá sau theo hợp đồng hành vi và bằng chứng.

Việc chưa có caller UI không tự cho phép xóa sessions, phrase overrides hay telemetry. Việc chưa tìm thấy caller trong repository cũng không tự cho phép xóa endpoint/bảng có thể được dùng bên ngoài.

## Testing Decisions

### Seam nghiệm thu được đề xuất

Ưu tiên một seam hành vi cao nhất: user nhập/dán trên workspace, quan sát kết quả/trạng thái/highlight, copy và xem lịch sử, đi qua backend thật trong môi trường kiểm thử cô lập. Giả lập provider AI ở ranh giới bên ngoài để tái hiện đúng/sai/quota/timeout/trả muộn một cách xác định; không mock bỏ chính sách chuẩn hóa đang được nghiệm thu.

Với quyền, kiểm thử trực tiếp API được xác thực là bắt buộc để không chỉ chứng minh nút bị ẩn. Đây là mặt kiểm tra an ninh của cùng hệ thống, không phải đề xuất thêm luồng sản phẩm.

Tái sử dụng các seam live-normalization, auth/history/dictionary API và UI hiện có trước khi thêm seam mới. Module nội bộ chỉ cần test thấp hơn khi lỗi đặc thù khó chẩn đoán ở đầu-cuối; không buộc test phản chiếu từng hàm hoặc từng bảng.

Confirmation: Chủ project đã xác nhận ngày 2026-09-06: “Đồng ý với ranh giới kiểm thử này”. Nghiệm thu qua workspace với backend thật trong môi trường cô lập, giả lập AI cho tình huống xác định và gọi API trực tiếp để kiểm tra quyền là quyết định đã chốt. Đánh giá chất lượng Kimi thật là đợt riêng sau khi đủ điều kiện.

### Thế nào là test tốt

- Kiểm tra hành vi bên ngoài và bất biến sản phẩm, không số lần gọi hàm nội bộ hoặc tên lớp.
- Mỗi ví dụ mô tả đầu vào, ngữ cảnh, vùng phải giữ và các kết quả chấp nhận được; phần bất định có thể chấp nhận giữ nguyên thay vì chỉ một đáp án AI.
- Phân biệt lỗi làm đổi nghĩa với bỏ sót sửa; không tối ưu tỷ lệ “số từ được sửa”.
- AI response giả lập kiểm tra cơ chế tiếp nhận, không chứng minh chất lượng Kimi thật.
- Không lấy confidence model hoặc tỷ lệ coverage code làm độ chính xác ngôn ngữ.
- Test với dữ liệu tổng hợp/được phép; không gửi lịch sử riêng hoặc dữ liệu nhạy cảm để chạy benchmark.
- Test thật với provider là đợt đánh giá riêng sau khi đủ điều kiện và được phép; ghi nhận model, cấu hình, phiên bản dataset/prompt, độ dài và điều kiện tải.

### Ma trận nghiệm thu hành vi

| Case | Hành vi phải chứng minh |
|---|---|
| AC-01: Viết tắt nhiều nghĩa, thiếu ngữ cảnh | AI tự chọn nghĩa hợp lý nhất và áp dụng với nhãn suy đoán khi chưa chắc; không có AI/đề xuất hợp lệ thì giữ nguyên; không tự lấy nghĩa dataset đầu tiên hoặc hỏi user. |
| AC-02: Ngữ cảnh giải thích ở đoạn trước | Đoạn sau xét được bằng chứng liên quan; chia chunk không khiến mất thông tin. |
| AC-03: AI quota/timeout/không sẵn sàng | Có phần chắc chắn; thiếu AI được hiển thị đúng; không đổi trả phí hoặc mất input. |
| AC-04: Không chunk nào được AI kiểm tra | Không hiển thị toàn văn đã AI kiểm tra, kể cả confidence trả về cao. |
| AC-05: Chỉ một phần văn bản được kiểm tra | Phạm vi còn thiếu được phân biệt; không xóa bất định toàn văn chỉ vì một chunk đạt ngưỡng. |
| AC-06: Gõ thêm trong khi request cũ chạy | Response và lịch sử không gắn nhầm phiên bản; output mới không bị ghi đè. |
| AC-07: Dán dài, nhiều đoạn, có emoji | Giữ ranh giới đoạn/khoảng trắng có ý nghĩa; chỉ xóa nội dung thuộc phạm vi. |
| AC-08: Ngoại ngữ, URL/email, C++/C#, 9/10, 50% | Nội dung được bảo vệ giữ đúng; không chèn khoảng trắng hoặc viết hoa bên trong. |
| AC-09: Phủ định và mức độ cảm xúc | Không đảo nghĩa hoặc tăng/giảm sắc thái bằng suy đoán; bản gốc còn để đối chiếu emoji. |
| AC-10: Câu ngắn có vấn đề | Vẫn được đánh giá nhu cầu AI; không bỏ qua chỉ vì một ngưỡng ký tự cũ. |
| AC-11: Dấu câu chưa đủ căn cứ | Không tự thêm ?/!; không coi đầu chunk hoặc wrap là đầu câu. |
| AC-12: Sáu loại thay đổi, từ lặp, sửa nhiều loại | Highlight đúng vị trí hai phía, có mô tả, phần xóa/thêm/whitespace truy vết được. |
| AC-13: Copy một phần hoặc hoàn tất | Văn bản thuần khớp output hiển thị, trạng thái chưa đủ rõ trước khi copy. |
| AC-14: AI tìm nghĩa mới | Áp dụng đề xuất hợp lệ cho văn bản hiện tại kể cả confidence thấp với nhãn suy đoán; tích lũy bằng chứng độc lập để tự dùng theo ngữ cảnh; admin xử lý ngoại lệ, có chống đếm trùng, thu hồi và kiểm tra mẫu. |
| AC-15: Admin duyệt/sửa/xóa từ điển | User tiếp theo nhận dữ liệu có hiệu lực; không resurrect nghĩa hết hiệu lực từ cache/bootstrap. |
| AC-16: User thử ghi nghĩa/sửa từ điển/quản lý tài khoản | API từ chối; không chỉ ẩn UI. |
| AC-17: User/admin thử đọc/xóa lịch sử riêng người khác | API từ chối theo chính sách ownership đã chốt. |
| AC-18: Rời trang/xóa input khi còn request | Không lưu input mới cùng output cũ; lịch sử một phần giữ trạng thái một phần. |
| AC-19: Không đồng ý gửi AI | Không gửi provider; dataset-only vẫn hoạt động và trình bày giới hạn. |
| AC-20: Nhiều user, request trùng, quota gần cạn | Giới hạn tổng và theo user có tác dụng; không gọi vô hạn; không rò dữ liệu qua cache. |
| AC-21: Đăng xuất/revoke | Token không tiếp tục được dùng như phiên hợp lệ theo chính sách server. |
| AC-22: Input chứa chỉ dẫn dành cho AI | Chuẩn hóa nội dung như dữ liệu, không thay chính sách hay sinh hành động ngoài phạm vi. |

### Prior art và bằng chứng hiện có

Có sẵn test live normalizer, semantic verifier, tokenizer, emoji, auth/API/repository, UI hook/component và E2E workspace. Tái sử dụng hạ tầng đó, nhưng sửa kỳ vọng trái mục tiêu như chọn nghĩa thủ công, nghĩa riêng hoặc chỉ highlight viết tắt khi bước triển khai được cho phép.

Review đã chạy 54 test chọn lọc với mạng AI tắt và đều pass; đồng thời tái hiện các lỗi bảo toàn văn bản và AI-verified ở cấp hàm. Đây là baseline kỹ thuật, không phải nghiệm thu specification.

Các chỉ số cần đo riêng: sửa đúng, sửa sai/làm đổi nghĩa, bỏ sót, bảo toàn ngoại ngữ/định dạng, độ đúng highlight, thời gian kết quả đầu tiên và hoàn tất, số call/token/quota, mức xử lý đầy đủ. Chưa chốt con số SLA, tỷ lệ chính xác hoặc user đồng thời khi chưa có dữ liệu đại diện.

## Out of Scope

- Viết lại văn bản sáng tạo, dịch ngoại ngữ hoặc suy đoán ý tác giả để làm câu trôi chảy.
- Buộc user giải nghĩa, chọn biến thể, tạo từ điển riêng hoặc sửa từ điển chung.
- Tự xuất bản nghĩa AI toàn cục không qua kiểm tra bằng chứng/ngữ cảnh hoặc xác nhận; không dùng confidence riêng lẻ làm điều kiện tự duyệt.
- Mặc định admin được đọc/xóa lịch sử riêng người khác.
- Nhập/xuất CSV/Excel, xử lý nhiều bản ghi độc lập hàng loạt, public API cho khách hàng ngoài.
- Tự động đổi sang API/model trả phí hoặc cam kết quota miễn phí vô hạn.
- Tự triển khai Kimi hoặc xin Python/key trong giai đoạn viết spec.
- Microservices, di chuyển database, cache phân tán hoặc thêm dashboard chỉ vì có bảng/wrapper sẵn.
- Xóa code/bảng/endpoint dựa riêng vào không thấy caller nội bộ.
- Mở rộng quyền quản lý user chưa được chủ project quyết định.
- Cam kết dùng hosted trial cho công việc thật hoặc dữ liệu không được phép.
- Tạo implementation tickets hoặc triển khai thay đổi trong bước xuất bản specification này.

## Further Notes

### Truy vết quyết định

| Nguồn đã chốt | Phần thể hiện trong specification |
|---|---|
| Q1: bảo toàn ý và giọng điệu | G-01; N-03/04/07; AC-09 |
| Q2: giữ nguyên bất định, không hỏi nghĩa | G-02/05; N-10/12; D-07; AC-01 |
| Q3: AI chủ động khi cần sau dataset | G-03; N-11; A-03; AC-10 |
| Q4: nghĩa → ngân sách → tốc độ | G-04; A-04/05/06 |
| Q5 ban đầu: admin duyệt mọi nghĩa; cập nhật 2026-09-07: tự dùng theo bằng chứng/ngữ cảnh, admin xử lý ngoại lệ | D-03/04/05; AC-14; chính sách dùng chung v1.2 |
| Q6: ưu tiên phân tích đánh giá khách hàng | Problem Statement; G-01 |
| Q7: realtime và phiên bản đầu vào | Luồng nhập tay; R-12; H-02; AC-06 |
| Q8: văn bản dài, tiến độ, copy một phần | Luồng dán; R-07/11; AC-05/07/13 |
| Q9: ngoại ngữ, ký tự có nghĩa, viết hoa | N-05/06/08/09; AC-08/11 |
| Q10: hai phía, sáu loại highlight | R-01–06; AC-12 |
| Q11: quyền lịch sử, thông báo gửi AI | Bảng quyền; H-01–06; A-07–09 |
| Q12: đánh giá bằng dữ liệu, chưa chốt số | Testing Decisions |
| Q13: hệ thống quản lý key/quota chung | A-02/04; AC-20 |
| Q14: dữ liệu phù hợp, có dataset-only | A-07–10; AC-19 |
| Q15: hai hình thức, chưa file/batch/API ngoài | Out of Scope |
| Q16: nhóm nhỏ có đăng nhập, khoảng 5.000 từ | Luồng dán; Testing Decisions |
| Cập nhật provider sau Q16 | A-01/11: Kimi K3 qua NVIDIA; Gemini không còn là lựa chọn mục tiêu |
| Review ALIGNED | Giữ dataset/AI seam, auth/session, ownership, moderation, phrase, cache và công cụ build/eval có ích |
| Review MISALIGNED/UNNECESSARY | Không giữ chọn nghĩa mặc định thiếu căn cứ, hỏi nghĩa, nghĩa riêng, quyền lịch sử rộng, trạng thái verified sai, lỗi định dạng |

### Các điểm còn mở — không tự chuyển thành requirement

1. **Nơi sử dụng thực tế:** chưa có xác nhận deployment/công cụ ngoài repository. Không được xóa hoặc cam kết tương thích chúng trước khi kiểm kê.
2. **Phạm vi trial:** chưa có xác nhận chỉ đánh giá nội bộ hay dùng output cho công việc thật. Phần này chặn kết luận đủ điều kiện vận hành hosted trial, không chặn việc mô tả chức năng chuẩn hóa.
3. **Kimi thực tế:** quota, credit, JSON/response, reasoning, latency và chất lượng tiếng Việt chưa được đo bằng tài khoản thật. Không suy model mới hoặc context lớn sẽ nhanh/chính xác hơn.
4. **Quyền quản lý user chi tiết:** khóa/mở khóa, cấp tài khoản, sửa thông tin, reset mật khẩu, đổi role và cách đăng ký/chấp thuận user chưa được chốt. Không tự triển khai tất cả.
5. **Vận hành dữ liệu:** schema thật, backup/restore, retention, scheduler, nguồn SQL/JSON và nhiều worker chưa được xác minh đầy đủ.
6. **Chỉ số định lượng:** cần dữ liệu đo đại diện trước khi chốt SLA, quy mô đồng thời hoặc tỷ lệ chất lượng.

### Bằng chứng điều tra và giới hạn

[Bản đồ điều tra](map.md), [API/quota NVIDIA](assets/nvidia-api-quota.md), [điều kiện dữ liệu NVIDIA](assets/nvidia-data-terms.md), [caller capability](assets/capability-inventory.md) lưu bằng chứng và câu hỏi còn mở. Chúng không thay thế các requirement ở tài liệu này.

Nguồn NVIDIA hiện xác nhận model/API nhưng không chứng minh client GLM tương thích. Điều khoản hosted trial liên kết từ model card giới hạn mục đích sử dụng và dữ liệu; không thể suy quyền dùng model thương mại thành quyền vận hành endpoint miễn phí cho production. Không coi thông báo đồng ý trong app là ngoại lệ cho điều khoản provider. [API chính thức](https://docs.api.nvidia.com/nim/reference/moonshotai-kimi-k3-infer), [điều khoản trial](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf).

### Quy tắc sử dụng specification

- Đây là nguồn mô tả trạng thái mong muốn trong phạm vi đã chốt. Code, schema, test và mô tả implementation cũ không được dùng để đảo ngược requirement này.
- Không đánh dấu các câu hỏi điều tra là đã giải quyết chỉ vì specification đã được xuất bản.
- Những phần mở chỉ được bổ sung bằng bằng chứng hoặc quyết định của chủ project; không lấp bằng giả định im lặng.
- Bước tiếp theo có thể dùng specification để chọn giải pháp và lập kế hoạch khi được yêu cầu. Việc xuất bản không phải lệnh triển khai.
