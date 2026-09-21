# Báo cáo review & bảo trì mã nguồn — 2026-09-22

> Phạm vi: toàn bộ mã nguồn do dự án quản lý (backend Python/FastAPI, frontend React/Vite,
> cấu hình, script, CI, tài liệu vận hành). Phương pháp: chạy baseline kiểm thử trước, sau đó
> 5 review agent độc lập (normalizer / API-auth-data / AI layer / frontend / portability),
> tổng hợp + kiểm chứng từng phát hiện bằng đọc code, đo lường và chạy test, rồi mới sửa.

## 1. Trạng thái ban đầu (baseline) và sau khi sửa

| Kiểm tra | Trước | Sau |
|---|---|---|
| Backend pytest | 604 passed + 39 subtests | **607 passed + 39 subtests** (3 test regression mới) |
| Backend ruff | pass | pass |
| Backend mypy | pass (16 file) | pass |
| Backend bandit | 2 finding (B101, B105) | **0 issue** |
| Frontend vitest | 47 passed nhưng **flaky 1 test (~2/20 lần chạy full suite)** | **48 passed** (1 test regression mới) |
| Frontend build | pass | pass |
| CI | chỉ chạy frontend | **thêm job backend** (pytest, ruff, mypy, bandit) |

## 2. Đã sửa (đã kiểm chứng bằng test)

### Backend — chức năng / dữ liệu

1. **Ghi lịch sử chết khi DB lỗi** (đã xác nhận — ảnh hưởng trực tiếp máy mới chưa cài SQL):
   `app/main.py` CLI chết ngay sau khi in kết quả nếu SQL Server không kết nối được;
   `POST /api/history` trả 500 thay vì 503. Đã bọc `app/api/routes.py` (503 + log) và
   `app/main.py` (cảnh báo rồi chạy tiếp) — khớp triết lý "telemetry lỗi không fail normalize".
2. **`/api/sessions/revoke-all` fail-open-mù** (đã xác nhận): DB lỗi → 200 `{"revoked": 0}`
   trong khi session cũ vẫn hiệu lực. `app/data_manager/new_tables_repo.py` giờ re-raise;
   route trả **503** khi DB lỗi (thao tác bảo mật không được nói dối thành công).
3. **Telemetry lockout nuốt exception im lặng** (đã xác nhận): `app/data_manager/user_repo.py`
   thêm `logger.warning(..., exc_info=True)` ở 3 chỗ — đúng quy ước SYSTEM_CONTEXT mục 11.4.
4. **`_parse_ai_response` crash 500 khi AI trả JSON hợp lệ không phải dict** (đã xác nhận
   bằng logic): `app/normalizer/diacritic_restorer.py` giờ trả về original + confidence 0.0
   (đi qua fallback rule-based), kèm `confidence: null`/không phải số → 0.0.
5. **`_coerce_confidence` nuốt giá trị 0** (đã xác nhận): `app/normalizer/phrase_index.py`
   — `value or 1.0` nâng 0 tường minh thành 1.0; giờ 0 được giữ nguyên.
6. **`future.set_result` không guard trong flight dedupe** (race hẹp):
   `app/ai/admission.py` thêm `if not future.done():` đối xứng với 2 đường exception.
7. **Bandit B101 ở `app/ai/admission.py`**: thêm `# nosec B101` (assert chỉ dùng cho mypy
   narrowing, `_deadline.set()` luôn seed). **B105 false positive** ở `_TOKEN_STRIP_CHARS`
   (chuỗi dấu câu bị tưởng password): thêm `# nosec B105` + chú thích.

### Backend — hiệu năng/khả năng bảo trì (giữ nguyên hành vi, đã chạy lại 607 test)

8. **Folded phrase index rebuild mỗi lần `_rule_restore`** (đo thực tế ~12,9ms/lần gọi):
   `diacritic_restorer.py` memoize theo identity của dict phrase dùng chung.
9. **`SequenceMatcher` tính lại trong vòng lặp spelling edit** (loop-invariant):
   `live_normalizer.py` hoist ra trước vòng lặp.
10. **`_find_folded_token` fold lại toàn văn bản cho mỗi expansion span**:
    `live_normalizer.py` fold 1 lần/`_populate_change_metadata` + `bisect` thay vì
    re-fold prefix mỗi span (tương đương toán học đã kiểm chứng; 607 test pass).
11. **Thiếu kiểm biên trong `_context_phrase_overrides`**: skip out-of-range thay vì
    IndexError giữa pipeline nếu mai này có builtin lệch độ dài.
12. **Thuộc tính chết `vietnamese_vowels`** (`pipeline.py`): xóa (0 tham chiếu).

### Frontend

13. **Test flaky "aborts an in-flight request and revalidates repeated text"**
    (`src/hooks/useLiveNormalize.test.tsx`, tái hiện ~2/20 lần chạy full suite, 0/12 khi
    chạy đơn): assertion cuối đọc `result.current.data` ngay sau `waitFor(fetch count)` —
    kết quả chỉ đến sau `response.json() → publish → setState → React scheduler flush`
    (task riêng, waitFor không chờ). Đã gộp assert fetch-count + kết quả vào **một**
    waitFor. Ý nghĩa test giữ nguyên (vẫn kiểm chứng abort #0/#1, 3 fetch, text đúng).
14. **NDJSON: event cuối không có newline bị bỏ** (`src/lib/api.ts`, medium): nếu server/
    proxy cắt không kèm `\n`, kết quả `complete` đã về đủ vẫn bị lỗi 502
    "Kết nối AI bị gián đoạn". Giờ flush decoder + parse tail; tail malformed giữ đúng
    hành vi cũ. Kèm test regression "accepts a completed AI event that arrives without
    a trailing newline".
15. **Regex biên câu tính 2 lần** trong `useLiveNormalize.ts`: tính 1 lần trước effect.
16. **Copy-timer không dọn** (`HighlightedSourceEditor.tsx`): timer mới hủy timer cũ +
    cleanup khi unmount (bản ở `NormalizedOutputPane` đã làm đúng).

### Portability / vận hành

17. **`backend/.env.example` (mới)**: biến env backend + mặc định an toàn, không secret
    (trước đây chỉ có `.env.quality.example` bị guard chặn đọc, và không có mẫu runtime).
18. **`README.md` (mới ở root)**: yêu cầu môi trường, 6 bước chạy từ đầu, lệnh kiểm thử,
    ghi chú corpus DataDauCau là optional.
19. **`backend/requirements.lock` (mới)**: pin cứng 20 dependency chính theo phiên bản đã
    kiểm chứng (requirements.txt vẫn là khoảng version).
20. **`.github/workflows/ci.yml`**: thêm job backend (Python 3.14, cài requirements.lock,
    pytest DB-free + ruff + mypy + bandit); frontend giữ nguyên. *Lưu ý trung thực: job
    chưa chạy thật trên GitHub Actions — cần push để xác nhận.*
21. **`scripts/start_demo_servers.ps1`**: bỏ đường dẫn Node cứng
    `C:\Program Files\nodejs\node.exe` → `(Get-Command node).Source`, chỉ fallback về
    đường dẫn cũ (máy này vẫn resolve cùng file — đã đối chiếu).
22. **`.gitignore`**: thêm rác pytest/sandbox (`.test_tmp/`, `.pytest_tmp*/`, …),
    `data/diacritic/backup/`, `.smoke/`, thư mục công cụ cục bộ, và **lưới chặn
    `.scratch/ai-semantic-fix/.probe_cred` + `**/.env`** không bao giờ vào Git.
23. **`frontend/package.json`** thêm `engines: node >=20`; thêm `frontend/.nvmrc` (22).
24. **`docs/ai-runtime.md`**: sửa 2 default lệch code (`AI_TIMEOUT_SECONDS` 10→90,
    `SEMANTIC_VERIFY_MAX_CHUNKS` 32→64, đối chiếu `config.py`), đồng bộ mốc Python.
25. **`README_setup_sqlserver.md`**: thay tên máy cụ thể `DESKTOP-75UB0LS` trong ví dụ
    bằng `<TEN-MAY-CUA-BAN>`.

## 3. Đã xác nhận nhưng CHƯA sửa (cần quyết định/điều kiện)

- **401 khi DB blip → frontend tự đăng xuất hàng loạt** (`dependencies.py` +
  `is_token_valid` fail-closed): cần tri-state valid/invalid/db-unavailable để trả 503.
  Chạm luồng auth nhạy cảm — để làm riêng có test đầy đủ.
- **`error_types` có thể tràn cột `NVARCHAR(500)`** (50×64 ký tự ≈ 3,3k): cần chốt chính
  sách (giảm `MAX_ERROR_TYPES` hay chặn tổng độ dài) vì đổi hành vi API.
- **Max_length thiếu** ở `PendingApprovalRequest.expanded`/`review_notes` vs cột DB.
- **Race submit pending tạo row trùng** + **race register → 500 thay vì 409** +
  **login trả token chết khi ghi session fail**: sửa nhỏ từng cái, cần test riêng.
- **Difflib full-text trên paste ~1MB** (worst-case bậc 2): cần đo với paste thật trước
  khi thay đổi — đụng metadata highlight, không đụng text.
- **Policy v6 thiếu guard ký tự Cc/Cf** (`review_policy.py`): nếu sửa phải bump
  `REVIEW_POLICY_VERSION` (cache key) theo quy ước.
- **Verifier deadline chỉ là soft gate**; **on_progress raise mất kết quả chunk**;
  **non-streaming chấp nhận content rỗng**; **connection pooling httpx**; **sqlite
  busy-timeout 0.2s**; **hard-code 1 tên model nemotron** (`client.py:492`).
- **Dead code đã xác nhận, chưa xóa**: `pending_service._merge_user_overrides`,
  `new_tables_repo.cleanup_expired` + `history_repo.log_error` (chỉ test gọi),
  `prompts.PHRASE_DISAMBIGUATE_TEMPLATE`, frontend `LiveInputEditor.tsx`,
  `useAIDisambiguation.ts` (+ `api.disambiguate`), test-only `VariantCardList`,
  `AmbiguityHighlighter`, `AmbiguityChoiceList`, `HighlightedOutput.tsx`.
  Không xóa vì workspace **không có git** — xóa là không hoàn tác được.
- **Dead config**: 3 setting semantic_verify_* đã biết + `phrase_min_freq`,
  `ai_fallback_to_rules`, `nvidia_reasoning_effort`, alias `ROOT_DIR`.
- **Cache `DiacriticRestorer` (async) không bao giờ hit** (tạo per request ở call site).
- **`clearResponseCache()` tên sai bản chất** (chỉ dispatch event), **checkbox "Ghi nhớ
  đăng nhập" không tác động**, **bootstrap error state chết** (`AuthContext.tsx:69`),
  **stale race `AdminModerationPage.handleView`**, **thiếu cancel flag** ở
  AdminDictionaryPage/HistoryPage, **validator lệch type** `workspaceSession.ts`.

Chi tiết từng mục (vị trí, bằng chứng) xem phần log của các review agent; các mục đã
trích dẫn đủ file:line ở trên.

## 4. Hướng dẫn chạy trên máy mới (đã ghi trong `README.md`)

1. Windows + Python 3.14 + Node ≥20 + SQL Server Express + ODBC Driver 18.
2. `python -m venv .venv` → `pip install -r backend/requirements.lock`.
3. Sao chép `backend/.env.example` → `backend/.env` (hoặc root), điền `SQL_*`,
   `AUTH_SECRET` (lệnh sinh có sẵn trong file mẫu).
4. Tạo DB theo `README_setup_sqlserver.md` (schema + seed).
5. `cd frontend; npm install`.
6. `powershell -ExecutionPolicy Bypass -File scripts\start_demo_servers.ps1`.

**Đã kiểm chứng thực tế**: toàn bộ lệnh test/build trên máy này (Python 3.14.5, Node 26).
**Chưa kiểm chứng**: clone thật (workspace chưa có git), GitHub Actions job backend
mới, cài đặt trên máy khác — các bước được đánh giá qua mã nguồn + tài liệu.

## 5. Danh sách file cho 3 mục đích

### 5.1. Backup .zip (khôi phục dự án)
- `backend/` TRỪ: `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `__pycache__`,
  `.pytest_tmp*`, `.pytest_dsh_sc*`, `.review_tmp*`, `.test_tmp_fresh`,
  `_tmp_admission_run`, `review_pytest*.txt`, `.coverage`, `data/DataDauCau` (2GB —
  quyết định riêng, xem dưới), `data/diacritic/backup/`, `data/diacritic/.checkpoints/`,
  `data/diacritic/.smoke/`, `data/runtime/dictionary-state.sqlite3` (cache, sinh lại được).
- `frontend/` TRỪ: `node_modules`, `dist`, `playwright-report`, `test-results`,
  `tsconfig.app.tsbuildinfo`.
- Root: `scripts/`, `docs/`, `README.md`, `README_setup_sqlserver.md`, `SYSTEM_CONTEXT.md`,
  `PRODUCT.md`, `DESIGN.md`, `ChuanHoaTiengViet.slnx`, `.gitignore`,
  `.github/workflows/ci.yml`, `.agents/skills/`.
- **Khó tái tạo — phải backup riêng**: `backend/data/DataDauCau/*.csv` (~2GB corpus,
  chỉ cần khi rebuild asset dấu), `backend/data/diacritic/` (asset 7.170 word_map +
  220k bigram + 202 builtin trong code — asset gốc có trong repo nhưng nếu đã rebuild
  thành công bản mới thì backup), DB SQL Server `VietNormalizer` (dữ liệu người dùng),
  và **`NVIDIA_API_KEY`/`AUTH_SECRET` thật — lưu trong password manager, KHÔNG vào zip**.

### 5.2. GitHub (commit lên repo cá nhân)
- Toàn bộ mã nguồn + config mẫu + docs như trên (giống 5.1, không gồm DataDauCau).
- Đã có trong `.gitignore`: `.env`, `.probe_cred`, rác pytest, backup asset.
- **Bổ sung khuyến nghị**: `.scratch/ai-semantic-fix/.probe_cred` tuyệt đối không commit
  (đã chặn bằng .gitignore); nếu muốn đẩy tool chẩn đoán trong `.scratch/ai-semantic-fix/`
  thì xem lại từng log để tránh lộ prompt/key nội bộ; `.scratch/pytest-rebuild-tmp/` bỏ.
- Cần cung cấp riêng cho thành viên: giá trị `SQL_PASSWORD`, `AUTH_SECRET`,
  `NVIDIA_API_KEY` (qua kênh riêng), corpus DataDauCau (nếu cần rebuild), DB dump.

### 5.3. Có thể cân nhắc xóa (cần shell admin vì khóa ACL — kiểm tra sau khi xóa: pytest vẫn pass)
- `backend/.pytest_tmp3..16` (14 thư mục), `backend/.pytest_dsh_sc`, `.pytest_dsh_sc2`,
  `backend/.test_tmp_fresh`, `backend/.review_tmp`, `.review_tmp2`, `.review_tmp3`,
  `.review_tmp4` (4 thư mục do phiên này tạo), root `.test_tmp`, `.dsh-pytest-tmp`,
  `.scratch/pytest-rebuild-tmp/`, `backend/_tmp_admission_run/` — toàn bộ là temp
  pytest/sandbox, không được tham chiếu bởi code (đã grep).
- `docs/evaluation/*.json` (14 file artifact đánh giá một lần) — hỏi owner trước.
- `ChuanHoaTiengViet/` (legacy VS project, `.pyproj` liệt kê ~20 file lỗi thời) —
  giữ nếu vẫn dùng Visual Studio; nếu không, xóa cả thư mục.
- `AnhMau/ChuanHoa.png` — vai trò chưa rõ (mockup?), **giữ lại** đến khi owner xác nhận.
- **KHÔNG xóa**: `backend/data/**` (asset + corpus), `.scratch/ai-semantic-fix/`
  (tool chẩn đoán + Test1/Test2 ground truth), `.agents/skills/`.
