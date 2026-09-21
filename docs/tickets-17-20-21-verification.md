# Nghiệm thu phạm vi ticket 17 → 20 → 21

Ngày: 2026-09-09. Phạm vi theo yêu cầu trực tiếp của chủ dự án trong phiên làm việc.

## Ticket 17

- Hoàn thiện hai bảng `ai_meaning_candidates`, `ai_meaning_evidence` trong script schema idempotent; thêm bảng audit riêng, scope fingerprint, user/session fingerprint và unique index context cho bằng chứng mới. Bản ghi cũ không có scope không được tự dùng chung.
- Repository dùng transaction và SQL Server `sp_getapplock` để tuần tự hóa thao tác ghi/đổi trạng thái giữa các worker, kể cả khi chưa có candidate. Một request hoặc nội dung đã gặp không tăng evidence. Cache, retry được đánh dấu và kết quả reuse không tự củng cố bằng chứng. Khi kết quả gồm cả chunk cache và chunk mới, chỉ corrections từ chunk mới được ghi.
- Policy `context-v1-3requests-2users-3sessions`: ít nhất 3 request/context độc lập; production cần 2 user, development cần 3 session. Chỉ tự nâng tới `conditional_shared`, không tự nâng `confirmed`.
- Phạm vi dùng lại bảo thủ: cùng abbreviation, domain và hai từ liền sau abbreviation; thiếu hai từ sau thì dùng hai từ liền trước. Abbreviation phải xuất hiện duy nhất để xác định scope. Trường hợp ngắn/không rõ scope vẫn ghi candidate, nhưng không tự nâng hoặc reuse. Đây là phép khớp ngữ cảnh xác định, không phải mô hình đo tương đồng ngữ nghĩa.
- Nghĩa cạnh tranh trong cùng scope chuyển cả hai sang `needs_review`. Admin phải thu hồi nghĩa cạnh tranh trước khi xác nhận nghĩa còn lại. Các scope khác nhau có thể cùng tồn tại.
- Fingerprint dùng HMAC-SHA256, namespace riêng cho user/session/request/context/scope; không lưu token, id user hay nội dung request thô vào evidence. Snippet chỉ giữ viết tắt và tối đa hai từ neo ngữ cảnh, che phần còn lại cùng từ viết hoa có khả năng là tên. Cần giữ `AUTH_SECRET` ổn định và giống nhau giữa các worker để nhận diện evidence xuyên phiên/process.
- API admin: `GET /api/admin/ai-meanings` (status/domain/abbr, offset/limit), `GET /api/admin/ai-meanings/{id}` (snippet đã che và audit), `POST /api/admin/ai-meanings/moderate` (tối đa 100 id, confirm/revoke, lý do bắt buộc). UI nằm trong trang kiểm duyệt, có lọc, phân trang, chọn nhiều mục, xem bằng chứng và audit. UI hiển thị giới hạn 100 evidence/200 audit gần nhất; database vẫn giữ toàn bộ audit.
- Mỗi chuyển trạng thái tăng revision. Thu hồi vô hiệu hóa live-data cache và tăng revision dùng chung; reuse đọc SQL ở request kế tiếp và kiểm tra revision trước khi trả kết quả, kể cả stream. Khi kiểm tra hiệu lực thất bại, không reuse. Bản ghi revoked không được tái kích hoạt từ evidence cũ hoặc inference mới. AI vẫn có thể suy luận cho phiên hiện tại; đó không phải khôi phục quyền reuse.
- Dataset-only không dùng candidate và không gọi AI. Nguồn `ai_conditional`/`ai_inferred`, candidate id, revision và policy version được giữ trong response/provenance khi có. Lỗi ghi evidence không làm mất output, nhưng phát warning có thể theo dõi và log không chứa ngữ cảnh.

Kiểm thử: repository trên database SQLite cô lập qua chính SQLAlchemy queries; API với dependency xác thực; luồng `/api/normalize/live` thực dùng dataset giả lập và AI giả. Bao phủ ngưỡng production/dev, copy/cache/retry/chunk cache, không đủ scope, conflict, rollback thao tác nhóm, quyền 401/403, audit/redaction, dataset-only, reuse không gọi model và revoke ngay trước/trong request. Không gọi provider thật.

Giới hạn nghiệm thu: chưa chạy migration hoặc kiểm thử khóa đồng thời trên SQL Server thật, chưa đo chất lượng nghĩa từ model thật, chưa đo tải production. Ngưỡng v1 là ngưỡng được yêu cầu, không phải kết luận chất lượng thống kê. Trước triển khai môi trường SQL Server hiện hữu, chạy `backend/database/init_schema.sql` bằng quy trình triển khai của dự án. Không xuất các candidate sang JSON/dataset và không tạo pipeline training.

## Ticket 20

- Giữ nguyên `backend/data/spelling/known_typos.json`.
- Fixture `backend/tests/fixtures/spelling_regression.json`: 3 positive, 9 negative, 2 mixed. Negative gồm không dấu, chữ đúng/title case, URL/email/mã, tên riêng, ngoại ngữ, từ hiếm/phủ định và ranh giới token. Hai mixed kiểm tra teencode và typo riêng biệt.
- Quy tắc chỉ nhận exact match ngoài protected literals; không sửa tên viết hoa chỉ vì case-insensitive match. Metadata phát sinh từ thao tác sửa: `kinds: ["spelling"]`, `reason: "known_typo"`, `confidence: 0.99`. Sau chuẩn hóa/AI, ánh xạ lại span và chỉ giữ provenance nếu phần sửa vẫn tồn tại đúng.
- UI dùng kinds/reason/confidence của backend để highlight và tooltip; không suy loại sửa từ diff. Offsets theo Unicode code point được xử lý đúng khi có emoji.
- Kết quả fixture: 5/5 positive + mixed đúng, 9/9 negative giữ nguyên tại bước spelling; tổng 6 sửa đúng, 0 sửa sai, 0 bỏ sót trong fixture. Không suy rộng thành độ chính xác chính tả tiếng Việt tổng quát.

## Ticket 21

- Module riêng `backend/app/normalizer/punctuation.py`, test độc lập. Chỉ nhận đầu câu `tại sao`, `vì sao`, `bao giờ`, `bao nhiêu` có nội dung phía sau. Không nhận `ai cũng...`, `gì cũng...`.
- Giữ nguyên câu có dấu, URL/email, số hoặc mã; thêm tối đa một `?`, không thêm `!`. Giữ khoảng trắng cuối; chạy lại không thêm lần hai. AI không được vượt chính sách bằng cách tự thêm/bỏ/đổi dấu câu.
- Metadata `kinds: ["punctuation"]`, `reason: "explicit_question_opening"`, source span rỗng, output span chỉ đúng dấu mới. Input có marker vị trí thêm không chứa ký tự text; output highlight `?`; kiểm thử clipboard xác nhận chỉ copy plain text.

## Các lệnh kiểm tra

Kết quả tại lần kiểm tra cuối: toàn bộ backend 520 passed, 1 skipped, 39 subtests; Ruff cho các module thay đổi đạt. Toàn bộ frontend ban đầu 40 passed; sau khi thêm kiểm thử clipboard, 12 test liên quan đạt (tổng hiện có 41 test). TypeScript/Vite production build đạt. Test skip đã có trong suite, không được coi là đã kiểm chứng.

```powershell
.venv/Scripts/python.exe -m pytest backend/tests -q -p no:cacheprovider
cd frontend
npm test -- --run
npm run build
```

Frontend cần chạy ngoài sandbox trên máy này vì esbuild bị chặn đọc cấu hình trong sandbox. Việc này đã được cho phép trong phiên. Cảnh báo còn lại trong pytest thuộc deprecation của Starlette/slowapi, không phải test thất bại.
