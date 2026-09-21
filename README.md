# Chuẩn hóa văn bản tiếng Việt

Hệ thống chuẩn hóa văn bản tiếng Việt kiểu chat: khôi phục dấu, mở rộng viết tắt,
gợi ý nghĩa cho từ lạ, kèm lớp AI hiệu đính **opt-in** (mặc định tắt).

- **Backend**: Python + FastAPI tại `backend/` (rule-based là luồng chính, không cần mạng).
- **Frontend**: React 19 + Vite tại `frontend/`.
- **Database**: SQL Server Express (dev) — hệ thống vẫn chạy ở chế độ fallback JSON khi DB chưa sẵn sàng, nhưng pending/history/moderation cần DB.
- **AI**: NVIDIA API (OpenAI-compatible) — chỉ dùng khi người dùng bật "Cho phép AI".

Bản đồ chi tiết kiến trúc, luồng xử lý và quy ước phát triển: xem [`SYSTEM_CONTEXT.md`](SYSTEM_CONTEXT.md).

## Yêu cầu môi trường

| Thành phần | Phiên bản đã kiểm chứng | Ghi chú |
|---|---|---|
| Windows | 10/11 | Script khởi động là `.ps1`/`.cmd` |
| Python | 3.14 | Chưa kiểm chứng trên 3.11–3.13; tooling cấu hình target py311 |
| Node.js | >= 20 (đã chạy trên 22 và 26) | Frontend dev/build/test |
| SQL Server | Express + ODBC Driver 18 | Xem `README_setup_sqlserver.md` |

## Chạy từ đầu trên máy mới

```powershell
# 1. Tạo venv Python (tại repo root)
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# 2. Cấu hình backend
#    Sao chép backend\.env.example thành backend\.env (hoặc .env ở root) và điền giá trị.
#    AUTH_SECRET để trống vẫn chạy (token chỉ mất hiệu lực khi restart).

# 3. Khởi tạo database (tùy chọn, xem README_setup_sqlserver.md)
#    - Tạo DB + schema: backend\database\init_schema.sql
#    - Seed từ điển:    cd backend; ..\.venv\Scripts\python.exe database\seed_from_json.py

# 4. Frontend
cd frontend
npm install

# 5. Chạy dev (cả hai server) — từ repo root
powershell -ExecutionPolicy Bypass -File scripts\start_demo_servers.ps1
# Backend : http://localhost:8000/api/health
# Frontend: http://localhost:5173
```

Không có auto-reload cho backend dev — sửa code backend xong phải restart server.

## Chạy kiểm thử

```powershell
# Backend (chạy từ thư mục backend/)
cd backend
..\.venv\Scripts\python.exe -m pytest tests -q
..\.venv\Scripts\python.exe -m ruff check app tests scripts database
..\.venv\Scripts\python.exe -m mypy
..\.venv\Scripts\python.exe -m bandit -r app scripts -q

# Frontend (chạy từ thư mục frontend/)
cd ..\frontend
npm test
npm run build
```

## Tài liệu khác

- `README_setup_sqlserver.md` — cài SQL Server, schema, seed.
- `backend/.env.example` — biến môi trường backend và mặc định an toàn.
- `frontend/.env.example` — cấu hình URL API cho production build.
- `docs/` — tài liệu vận hành AI runtime, chất lượng full-text, quy ước agent.
- `SYSTEM_CONTEXT.md` — kiến trúc, luồng normalize, quy ước sửa logic chuẩn hóa.

## Corpus build lại asset dấu (tùy chọn)

Thư mục `backend/data/DataDauCau/` chứa corpus 2GB **không đi theo repo**
(`.gitignore` loại trừ `sample_5k.csv`). Asset runtime trong `backend/data/diacritic/`
đã có sẵn, normalize hoạt động bình thường mà không cần corpus; chỉ cần khi
rebuild asset qua `scripts/rebuild_diacritic_assets.ps1`.
