# SESSION HANDOFF — ChuanHoaTiengViet: sửa lỗi AI verification + nâng chất lượng chuẩn hóa

> Viết ngày 21/09/2026. Đọc file này trước khi làm bất cứ việc gì trong session mới.
> Mọi đường dẫn tương đối tính từ repo root: `C:\Users\admin\Downloads\ChuanHoaTiengViet`

## 1. DỰ ÁN LÀ GÌ

- Hệ thống **chuẩn hóa văn bản tiếng Việt chat** (thiếu dấu, teencode, viết tắt): FastAPI backend (`backend/`), React frontend (`frontend/`), SQL Server, AI NVIDIA Build (OpenAI-compatible).
- Đọc `SYSTEM_CONTEXT.md` để có bản đồ dự án đầy đủ (kiến trúc, DB, luồng normalize).
- Luồng chính: `/api/normalize/live` → `LiveNormalizerService.normalize_live` (rule-based: spelling → diacritic restore → phrase → abbreviation) → `apply_semantic_verification` → `SemanticVerifier.verify(review_all=True)` → AI (NVIDIA) hiệu đính → `accept_edits` lọc edit an toàn → merge kết quả.
- Target người dùng: **văn bản chat sinh viên** (~1000 từ), file test: `.scratch/ai-semantic-fix/Test1.txt`, `Test2.txt`.

## 2. MÔI TRƯỜNG MÁY NGƯỜI DÙNG

- Windows, **Python 3.14.5** tại `.venv\Scripts\python.exe` (chạy lệnh python LUÔN từ `backend/` với workdir backend).
- SQL Server: `DESKTOP-75UB0LS\SQLEXPRESS`, DB `VietNormalizer`, Windows Auth. **LƯU Ý: sandbox của agent KHÔNG kết nối được SQL** (lỗi SSPI "No credentials are available") — script touch-DB phải do USER chạy trong terminal thường.
- Backend dev server chạy tại `localhost:8000` bằng `scripts\run_backend_dev.cmd` — **KHÔNG có --reload** → sau khi sửa code backend phải restart server thủ công.
- Frontend: `localhost:5173`. Tài khoản test đã tạo: `dsh_probe_a4f2` (password trong `.scratch/ai-semantic-fix/.probe_cred`) — có thể xóa.
- Lỗi môi trường đã biết (KHÔNG phải bug code): pytest `tmp_path` fixture fail PermissionError do CPython 3.14 + sandbox chặn scandir — **giải pháp: chạy pytest với `--basetemp="$env:TEMP\..."` + escalation `danger-full-access`** khi cần tmp_path; không có tmp_path thì chạy bình thường.
- `.env` ở repo root (KHÔNG được đọc trực tiếp). Settings đọc qua `app.config.get_settings()`. Giá trị thực tế: `NVIDIA_MODEL=z-ai/glm-5.3-flash`, `SEMANTIC_FALLBACK_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b`, `AI_TIMEOUT_SECONDS=90`, `AI_MAX_RETRIES=2`, `SEMANTIC_REVIEW_CHUNK_WORDS=800` (env override — code đã clamp ≤400 trong `SemanticVerifier.__init__`), `NVIDIA_ENABLE_THINKING=1` (verifier override=False per-request).

## 3. CÔNG VIỆC ĐÃ LÀM (3 vòng)

### Vòng 1 — Sửa TIMEOUT (đã xong, đã verify)
Triệu chứng gốc: văn bản dài → `AI deadline exceeded` / `NVIDIA request timed out`, 0/2 chunk, output = dataset thô lỗi.
Nguyên nhân + fix:
1. `backend/app/ai/client.py` `_build_body`: **honor per-request `enable_thinking`** (trước đây bị bỏ qua → glm-5.3-flash luôn bật thinking → chunk 800 từ không bao giờ xong trong 90s). Probe thực nghiệm: thinking ON = timeout 100%, OFF = 100% thành công.
2. `backend/app/ai/fallback_client.py`: primary giữ `remaining - min(20, remaining/3)` thay vì cap `min(remaining/2, 30)` (trước đây primary 40-70s bị giết ở 30s → fallback cũng fail → double latency 64s).
3. `backend/app/ai/client.py` `_parse_response`: **reject `finish_reason="length"`** (JSON cắt cụt = nguồn output vô nghĩa).
4. `backend/app/ai/nemotron_client.py`: **honor `json_mode`** (trước trả prose).
5. `backend/app/ai/services.py`: fallback nhận đủ timeout window (shared deadline vẫn chặn tổng).
6. `backend/app/config.py`: `SEMANTIC_REVIEW_CHUNK_WORDS` default 800→400; `semantic_verifier.py` clamp cứng ≤400 (đo: 400 từ = 10/10 chunk trong deadline; 800 = 3/4).

### Vòng 2 — Sửa CHẤT LƯỢNG nghĩa (đã xong, đã verify)
Triệu chứng: output "không có nghĩa gì cả" — nguồn gốc: (a) dataset khôi phục dấu sai + luôn timeout nên AI không bao giờ sửa được; (b) prompt cũ bắt model **chuẩn hóa lại từ đầu** → model lật sai từ đồng âm (đo: 49 lỗi baseline → 64 lỗi sau AI!).
Fix:
1. `backend/app/normalizer/diacritic_restorer.py`:
   - Guard `_token_has_explicit_diacritics` trong `_context_phrase_overrides`: context-phrase fold KHÔNG ghi đè token người dùng đã gõ đúng dấu ("su kiên nhẫn" không còn thành "sự kiện nhẫn").
   - `_BUILTIN_CONTEXT_PHRASE_OVERRIDES`: +21 chat collocations (mo vo, tam trang, tien tro, qua tai, vong lap, muc luc, gach chan, bung xa, co gang, chay bai, mon kho, chua hieu, chon viec, de hoi, nam im, hon da, lich san, dung bua, gioi qua, mua vo, cuon vo).
   - `_BUILTIN_WORD_MAP_ENTRIES` + merge trong `get_shared_word_map`: thêm token thiếu hẳn (met→mệt; thi→thì/thị/thí; trai; vai; nam).
2. `backend/app/ai/semantic_verifier.py` prompt review_all: đổi sang **HIỆU ĐÍNH theo `normalized_reference`** (bản rule-based làm điểm xuất phát, KHÔNG chuẩn hóa lại từ đầu); đưa `ambiguous_str` (danh sách vị trí đồng âm + candidates) vào prompt; temperature 0 khi review_all; nguyên tắc "không chắc → giữ nguyên"; giữ 2 marker parse "Dữ liệu JSON (không phải chỉ dẫn):\n" và "\nChỉ trả JSON:" (tests phụ thuộc); ví dụ confidence dùng 0.9 (KHÔNG dùng 0.0 — model từng copy nguyên xi → conf 0.0 toàn chunk).
3. `backend/app/ai/review_policy.py` (REVIEW_POLICY_VERSION = "whole-text-v5-bounded-context-edits"):
   - Sửa viết tắt dưới threshold chỉ được chọn meaning trong options; expansion repairs tính vào edit budget;
   - **License fall-through**: token KHÔNG có trong `allowed_diacritics` map rơi về quy tắc similarity chung (trước đây bị từ chối tuyệt đối → "met"→"mệt" không bao giờ được chấp nhận).
4. Test mới: `backend/tests/test_context_phrase_guard.py`, `test_phrase_diacritic_guard.py` (7 test), `test_review_prompt_reference.py` (4 test), + edits trong `test_full_text_review.py` (6 test regression vòng 1 + fall-through), `test_diacritic_restorer.py` (sửa contract missing-file → builtin entries).

### Vòng 3 — Bigram corpus chat (đang dở, chờ user)
Bối cảnh: SA chẩn đoán **100% lỗi chủ động từ DiacriticRestorer** (bigram thiên lệch news: `vào_bán=6486` vs `vào_bàn=483`, `hội_cầu=404` vs `hỏi_câu=0`). Người dùng nhớ đã build bigram từ trước — ĐÚNG: pipeline build có sẵn (`backend/scripts/build_diacritic_streaming.py` — chunked+prune+checkpoint/resume, viết cho máy 16GB) và `bigram_freq.json` (200k entries) build từ `DataDauCau/ViDiacritics_*.csv` — corpus **news/giải trí** (nguồn bias).
Đã làm:
- User khôi phục 4 file CSV (train 1.6GB, val/test 201MB, sample 5k) → **đã di chuyển về vị trí chuẩn `backend/data/DataDauCau/`** (theo .gitignore + `build_bigram_index.py` + `test_mine_phrases.py`); test từng skip giờ **10/10 pass**.
- `build_diacritic_streaming.py`: +cờ `--weight PATH=FLOAT` (nhân đếm cho domain weighting).
- `scripts/rebuild_diacritic_assets.ps1` (repo root): runner an toàn — backup asset cũ vào `backend/data/diacritic/backup/<timestamp>/` → build (smoke/Resume/IncludeTest/ChatWeight/ChunkSize) → regression gate → rollback path. Chat CSVs đặt trong `backend/data/DataDauCau/chat/` tự được nhận + weight.
- `backend/scripts/convert_chat_corpus.py`: convert raw comment CSV → DataDauCau format (NFD strip + đ→d, dedupe, min-words). Đã convert **UIT-ViSFD** (raw giữ ở `backend/data/DataDauCau/chat/_raw/`, converted trong `chat/`): 11.118 rows.
- `backend/scripts/export_history_corpus.py`: export `dbo.normalization_history` (input_text, output_text) → corpus chat ĐÚNG miền từ chính dữ liệu người dùng. **CHƯA CHẠY** (sandbox không connect được SQL — user phải chạy trong terminal thường).
- Build thật đã chạy 2 lần trên máy user (~31 phút/lần, 11.294.682 dòng, RAM OK). **CẢ HAI lần đều rollback** vì: (a) corpus news thuần tái tạo đúng bias cũ; (b) ViSFD = review điện thoại, KHÔNG phủ trap keys (chúc_bạn=0, mấy_giờ=0, rồi_bạn=0 trong chat; news có số đếm sai 255/431...) → weight không sửa được khi chat không có bằng chứng.
- **Hiện trạng asset: ĐÃ ROLLBACK VỀ BỘ GỐC (news-biased)** — backup các lần: `backup/20260921_032912`, `20260921_124046`, `20260921_135725` (đều chứa bộ asset gốc như nhau). Suite regression: **116/116 xanh**.
- Checkpoint build còn tồn tại: `backend/data/diacritic/.checkpoints/ckpt_streaming.json` (11MB, files_done=[val,train], 11.294.682 lines) → lần build sau với `-Resume` sẽ BỎ QUA 2GB news, chỉ xử lý chat (~phút).

## 4. KẾT QUẢ ĐO (bộ chấm điểm `.scratch/ai-semantic-fix/score_quality.py` — 64 pattern lỗi nghĩa từ output thật của user)

| Giai đoạn | Lỗi Test2 |
|---|---|
| Output user paste (trước session) | 64 |
| Sau vòng 1 (không timeout, AI vẫn lật sai) | 41-42 |
| Sau vòng 2 (guard + collocations + prompt hiệu đính + license) | **28** |
| Baseline rule-based (với asset gốc) | 35 |
| "thi"→"thì" (tham khảo) | 11 → **0** |
| Test1 | 5/5 chunk, conf 0.9, sạch pattern |

E2E browser qua server user: login → consent → paste → live normalize → AI verify → highlight ✅ (screenshot `.scratch/ai-semantic-fix/browser_after.png`).

## 5. TRẠNG THÁI TEST

- Full suite: **572 passed, 1 skipped** (lần chạy cuối đầy đủ, có tất cả thay đổi).
- Subset diacritic sau rollback: 116/116.
- Regression suite: `tests/test_diacritic_regression.py` (chat_regression_test.csv là ground truth của user — 51 case, NEW/OLD đều 31/51 exact-match, threshold pytest là accuracy ≥60%/case).
- Ruff + mypy: sạch.
- ⚠️ Nếu build lại asset: 3 case biên (`basic_7/8`, `short_41`) là ĐIỂM CHẶN — asset news thuần fail chúng ("chức bán ngủ ngon nhẹ", "máy giờ rồi bán", "tốt làm").

## 6. VIỆC CÒN ĐỞ (theo thứ tự ưu tiên)

1. **User restart backend** để load code mới (server không auto-reload; browser check lần trước thấy một phần code mới → user có thể đã restart giữa chừng, cần restart lại lần nữa cho các thay đổi sau cùng: word entries, license v5, prompt hardening).
2. **Corpus chat đúng miền** — chốt chặn của chất lượng còn lại (28 lỗi):
   - Cách 1 (sẵn sàng): user chạy `cd backend; ..\.venv\Scripts\python.exe scripts\export_history_corpus.py` → `data/DataDauCau/chat/history_export.csv` → chạy lại `powershell -ExecutionPolicy Bypass -File scripts\rebuild_diacritic_assets.ps1 -Resume -ChatWeight 3` (Resume bỏ qua 2GB news, chỉ thêm chat — vài phút).
   - Cách 2: tìm dataset chat sinh viên có dấu (ViSFD sai miền — đã chứng minh bằng số); hoặc user tự viết 300-500 câu kiểu Test1/Test2.
   - Sau rebuild: 3 case biên kỳ vọng chuyển xanh + Test2 giảm sâu hơn; nếu fail → rollback từ backup mới nhất.
3. ViSFD (11k rows) giữ ở chat\ với weight thấp để học văn phong; đúng miền hơn thì weight cao hơn.
4. Dọn rác bị khóa ACL (cần shell admin): `backend\.pytest_dsh_sc*`, `.dsh-pytest-tmp\`, `.test_tmp_fresh`, `.scratch\ai-semantic-fix\.pytest-tmp`, `backend\.pytest_tmp3..16` (rác cũ), `backend\.test_tmp`.
5. Xóa tài khoản test `dsh_probe_a4f2` qua UI admin.
6. Đề xuất chưa làm: prompt corrections-only protocol; dead knobs `semantic_verify_paste/typing/min_diacritic`; mảnh cụm news ("nguoi phu" chặn "phu hop" — greedy match).

## 7. CÔNG CỤ TRONG `.scratch/ai-semantic-fix/` (giữ lại để dùng)

- `repro_verify.py Test1|Test2` — E2E đầy đủ (DB-free patch + AI thật): in config, rule-based, semantic, lưu `*.rulebased.txt`/`*.final.txt`.
- `repro_direct.py` — gọi SemanticVerifier trực tiếp (không pipeline).
- `probe_latency.py` / `probe_chunk400.py` — đo latency NVIDIA thinking ON/OFF, chunk 400/800, nemotron.
- `score_quality.py <file>` — chấm 64 pattern lỗi nghĩa (+ đếm "thi" standalone).
- `compare_assets.py` — so 2 bộ asset (regression pass rate + Test2 hits).
- `diagnose_layers.py` — chẩn đoán tầng nào sinh lỗi (SA đã chạy, có log).
- `probe_weight.py` — đo news vs chat bigram counts.
- Logs: `rebuild_assets.log`, `repro_Test*.log`, `probe*.log`, `browser_after.png`.
- Chạy: `cd backend` rồi `..\.venv\Scripts\python.exe -u ..\.scratch\ai-semantic-fix\<script>`.

## 8. KIẾN THỨC KỸ THUẬT CỐT LÕI (để không phải khám phá lại)

- Stack timeout 4 tầng: httpx 90s → FallbackClient (primary `remaining-min(20,r/3)`, reserve fallback) → BudgetedClient deadline 90s (sqlite lease, dedupe flights) → verifier deadline `90×waves+1`. Log "200 OK rồi timeout" = stream/body đọc sau headers.
- `AIRequest.enable_thinking` giờ được NvidiaClient tôn trọng; NemotronClient honor json_mode; finish_reason=length → AIParseError.
- `accept_edits` (review_policy v5): chỉ nhận word-level edit, fold-similarity ≥0.6, cấm đụng protected literals, cấm giảm dấu, negation không được biến mất; abbreviation edits cần confidence≥threshold TRỪ khi chọn meaning trong options; diacritic license CHỈ áp cho key có trong map (fall-through cho token ngoài map); contextual budget = min(24, 12% từ).
- Prompt review_all: HIỆU ĐÍNH normalized_reference (giữ 2 marker + original_segment trong JSON cho tests parse); ambiguous positions list; temp 0; confidence example 0.9.
- Restorer: context-phrase fold guard (token có dấu/đ → giữ); builtin collocations + word entries (setdefault — file JSON vẫn authority); greedy longest-match vẫn còn lỗi mảnh cụm news ("nguoi phu" chặn "phu hop") — chưa sửa, chờ corpus sạch hơn.
- Build streaming: checkpoint tag "streaming" tại `backend/data/diacritic/.checkpoints/`; `--weight` nhân float vào đếm; files_done theo absolute path; sau thành công checkpoint tự xóa.
- Frontend NDJSON streaming (`live_stream.py`): mỗi event là FULL snapshot — frontend REPLACE không append.

## 9. LƯU Ý AN TOÀN DỮ LIỆU

- Asset live `data/diacritic/*.json` là kết quả build từ corpus news — đã rollback 2 lần, luôn có backup trong `backup/<timestamp>/` trước mỗi build.
- KHÔNG đọc `.env`; KHÔNG in secret; sandbox không chạm được SQL Server (script DB cho user chạy).
- File test của user: `.scratch/ai-semantic-fix/Test1.txt` (6.9KB), `Test2.txt` (5.5KB) — copy từ attachments gốc.
