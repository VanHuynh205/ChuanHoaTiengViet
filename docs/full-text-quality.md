# Chất lượng chuẩn hóa toàn văn — 2026-09-09

## Kết quả và phạm vi

Đã thay cơ chế kiểm tra theo danh sách từ mơ hồ bằng kiểm tra toàn văn khi người dùng bật AI. Không thêm câu mẫu của người dùng vào seed hoặc bảng thay thế runtime. Văn bản được cung cấp chỉ nằm trong fixture đánh giá, tách khỏi dữ liệu chuẩn hóa.

Cấu hình chất lượng đã áp dụng vào `.env` hiện hữu và có mẫu tại `backend/.env.quality.example`:

| Thiết lập | Giá trị |
|---|---|
| Provider hiện tại | NVIDIA |
| Model chính | `google/gemma-4-31b-it` |
| Thời hạn một lượt model chính | 90 giây |
| Model dự phòng cho kiểm tra toàn văn | `nvidia/nemotron-3.5-lightning-30b-a3b` |
| Thời hạn lượt dự phòng | Tối đa 30 giây |
| Kích thước mục tiêu mỗi phần | 400 từ; ưu tiên ranh giới câu/đoạn |

Việc dùng AI vẫn cần người dùng bật lựa chọn AI. Các giới hạn request/concurrency hiện hữu vẫn áp dụng. Fallback chỉ dùng khi lỗi mạng, lỗi phản hồi hoặc timeout; không dùng để vượt lỗi quyền hoặc quota. Backend cần đọc lại cấu hình khi khởi động; phiên làm việc này không tìm thấy dịch vụ đang nghe ở 8000/5173 để khởi động lại.

## Nguyên nhân đã tái hiện

1. Frontend không gửi lượt AI nếu dataset trả `not_needed`. Backend và verifier cũng trả sớm khi không có candidates. Vì thế từ đúng riêng lẻ nhưng sai trong câu không được xét.
2. AI nhận bản đã sửa dấu sai, dễ bám theo nghĩa sai. Bản gốc chưa được căn chỉnh thành ngữ cảnh tham chiếu cho từng phần.
3. Ngân sách phản hồi cũ có thể chỉ 256 token, với trần verifier 2048. Đã quan sát phản hồi kết thúc vì `length` và timeout thật. JSON không hoàn thành dẫn tới giữ lại bản rule-based.
4. Model Nemotron đang cấu hình vẫn tạo nhiều lỗi ngữ nghĩa trên các ca đa chủ đề, kể cả khi đã gửi toàn bộ phần cần xử lý.
5. Bộ quy tắc có thể đổi tên viết hoa liên tiếp và mất dấu phẩy khi mở rộng cụm; những lỗi này cần sửa trước khi AI kiểm tra.

Feedback loop ban đầu: `python -m pytest backend/tests/test_full_text_review.py -q -p no:cacheprovider` thất bại 3 ca vì không có lời gọi provider dù đã gọi bước AI. Các ca này hiện đạt.

## Cơ chế đã thay đổi

- Khi bật AI, mọi phần văn bản đều được xét, không phụ thuộc tín hiệu OOV/ambiguity. UI hiển thị số phần đã kiểm tra, kể cả kết quả hoàn tất.
- Chia văn bản theo ngữ cảnh, gom các đoạn ngắn để tránh tốn một lượt cho mỗi dòng. Không viết hoa chỉ vì bắt đầu một chunk. Khi chạm quota/số chunk hoặc lỗi, trạng thái phản ánh phạm vi chưa hoàn thành.
- Đối chiếu vị trí trong bản gốc với bản nền bằng căn chỉnh token; gửi đoạn gốc cùng ngữ cảnh trước/sau. Model chuẩn hóa từ bản gốc thay vì tin bản máy đã sửa. Bản tham chiếu được đặt dưới dạng dữ liệu, không phải chỉ dẫn.
- Output chỉ chứa đoạn cần xử lý. Ngân sách JSON có tối thiểu đủ dùng cho câu ngắn và tăng theo độ dài, trong trần cấu hình. Chế độ suy luận/sampling được chọn theo contract model; không gửi tham số của Nemotron cho Gemma.
- Nhận các sửa từ/cụm một cách cục bộ. Không cho phép tự chèn/bỏ ý, đổi số/literals, bỏ phủ định, sửa tên rõ ràng hoặc thay layout/dấu câu. Một teencode confidence thấp không mở quyền sửa cả đoạn với confidence thấp.
- Nghĩa do dataset mở rộng sai vẫn có thể được AI sửa trong đúng span, với đối chiếu từ viết tắt gốc. Spans highlight được căn chỉnh lại khi nghĩa thay đổi.
- Bảo vệ tên gồm các từ viết hoa liên tiếp ngay ở bước sửa dấu; phục hồi dấu kết thúc/ngăn cách có sẵn nếu bước mở rộng cụm làm rơi dấu. Không phát minh dấu mới từ quy tắc này.
- Giữ phần đã sửa hợp lệ nếu chunk khác gặp lỗi. Nếu dùng model dự phòng, status phản ánh việc đó và evidence giữ model thực sự tạo nghĩa. Các cơ chế chống evidence trùng, thu hồi và kiểm tra revision của ticket 17 vẫn hoạt động.

## Đo bằng provider thật

Bộ cố định: `backend/tests/fixtures/full_text_quality.json`, 12 ca / 256 từ tham chiếu, gồm không dấu, typo theo ngữ cảnh, teencode, văn bản đúng, tên/literals, ngoại ngữ và đoạn văn. Ba ca `school`, `food`, `meaning` dùng để khảo sát model; chín ca còn lại không dùng để chọn model ban đầu.

| Phạm vi | Nemotron sau cải tiến luồng toàn văn | Gemma ưu tiên chất lượng |
|---|---:|---:|
| Toàn bộ 12 ca | 27 lỗi từ / 256 từ | 7 lỗi từ / 256 từ |
| 9 ca chưa dùng chọn model | 15 lỗi từ / 189 từ | 6 lỗi từ / 189 từ |

Lỗi từ tính bằng khoảng cách chỉnh sửa token so với một bản tham chiếu đã viết trước. Có thể phạt cả phương án diễn đạt chấp nhận được; đây không phải thước đo ngữ nghĩa toàn diện hoặc ước lượng độ chính xác cho mọi văn bản tiếng Việt. Các ca lỗi dịch vụ vẫn được tính bằng bản nền thật mà người dùng nhận được, không bị loại khỏi bảng. Có 3 timeout trong nhóm Gemma; không coi chúng là lượt đã kiểm tra thành công.

Tóm tắt máy đọc được: `docs/evaluation/quality-summary.json`. Dữ liệu chi tiết:

- `full-text-direct-evaluation.json`: Nemotron, toàn bộ 12 ca và bài dài.
- `full-text-gemma-probe.json`: 3 ca khảo sát model.
- `full-text-quality-heldout-a.json`, `full-text-quality-heldout-b.json`: 9 ca đánh giá tiếp theo, gồm lỗi dịch vụ.
- `full-text-model-comparison.json`, `full-text-mistral-probe.json`: các phương án không được chọn vì timeout/lỗi/quota.
- `provider-models.json`: catalogue được đọc từ API NVIDIA trong phiên; không giả định mọi model trong catalogue đều phục vụ ổn định.

## Văn bản dài của người dùng

`full-text-user-final.json` lưu lượt provider thật với cấu hình Gemma và dự phòng: **5/5 phần được kiểm tra**, khoảng **164,7 giây**, 5 lượt logic, toàn bộ phần hoàn thành bằng model chính. Không có bản tham chiếu đầy đủ cho bài này nên không công bố WER/độ chính xác của nó.

Đã phát lại đúng các phản hồi provider đã lưu qua mã cuối để kiểm tra sửa layout mà không gọi AI lại: `full-text-user-replay.json`. Thời gian replay không đại diện latency provider.

Bản để đọc/so sánh: `docs/evaluation/user-text-normalized.txt`. Các lỗi trong ảnh như “kết quả lâu”, “nhạc nhau”, “ít những chất”, “không cần đọng” đã được sửa theo ngữ cảnh. Các đoạn còn lại cũng được xử lý bởi cùng cơ chế, không có rule riêng cho bài này.

## Tái chạy

```powershell
# Từ root: kiểm thử cơ chế, không gọi provider thật.
.venv/Scripts/python.exe -m pytest backend/tests -q -p no:cacheprovider

# Từ backend: benchmark thật, dùng cấu hình/khóa sẵn có và shared budget.
../.venv/Scripts/python.exe -m scripts.eval_full_text --online --sample --modes dataset,whole_text --fallback nvidia/nemotron-3.5-lightning-30b-a3b --output ../docs/evaluation/new-run.json

# Replay phản hồi đã lưu, không gọi provider.
../.venv/Scripts/python.exe -m scripts.eval_full_text --sample --ids user_sample --modes dataset,whole_text --replay ../docs/evaluation/full-text-user-final.json --output ../docs/evaluation/replay.json
```

Evaluator đọc dataset file; không ghi bảng user/history/candidate/SQL vận hành. Nó lưu text/prompt đánh giá trong report cục bộ, không lưu khóa hoặc header xác thực. Số token usage do provider cung cấp có thể thiếu; không suy ra chi phí bằng 0 từ trường thiếu/0.

Kiểm tra mã cuối: **543 backend test đạt, 1 skip, 39 subtests; 42 frontend test đạt; Ruff, Mypy (14 file AI), TypeScript/Vite build đạt**. Replay bài dài qua mã cuối vẫn kiểm tra đủ 5/5 phần; đã xác nhận dấu phẩy có sẵn được giữ trong bản xuất. Đã đọc lại cấu hình và xác nhận factory tạo SemanticVerifier dùng FallbackClient với model/thời hạn trong bảng trên.

## Giới hạn còn lại

Chất lượng model đã tốt hơn trong bộ thử nhưng chưa hoàn hảo. Gemma chậm hơn, có timeout; model dự phòng có chất lượng thấp hơn. Bộ đánh giá nhỏ, có vài ngữ cảnh đa nghĩa và chưa là corpus đại diện cho mọi lĩnh vực. Không có thay đổi nào ở đây tự chấp thuận candidate AI thành dataset chung hoặc triển khai production SQL.
