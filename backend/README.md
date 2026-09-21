# Backend — He thong chuan hoa tieng Viet

Toan bo phan backend (Python/FastAPI, du lieu, schema SQL, script, test) nam trong thu muc nay.
Frontend React o `../frontend`, script khoi dong dev cho ca hai server o `../scripts`.

## Cau truc

```
backend/
├── app/                 # Ma nguon FastAPI + CLI
│   ├── ai/              # NVIDIA client, semantic verifier, disambiguator, cache
│   ├── api/             # routes, schemas, dependencies, server (create_app)
│   ├── auth/            # bcrypt + JWT HS256 + session service
│   ├── data_manager/    # repositories SQL Server + JSON bootstrap + pending service
│   ├── normalizer/      # lõi chuẩn hóa: phrase, abbreviation, diacritic, emoji, pipeline
│   ├── utils/           # logger, text utils, diacritic detect
│   ├── bootstrap.py     # factory pipeline dùng chung cho CLI và API
│   ├── config.py        # Settings (đọc .env), validate cho production
│   └── main.py          # CLI entrypoint (run_cli)
├── data/                # Asset runtime: abbreviations, dictionaries, diacritic, emoji, phrases
├── DataTuVietTat_and_TuDienTiengViet/   # Bộ dữ liệu gốc (legacy fallback của json_sync)
├── database/            # init_schema.sql (idempotent) + seed_from_json.py
├── scripts/             # Script build asset / mining / eval / convert dữ liệu
├── tests/               # pytest — mirror cấu trúc app/
├── pyproject.toml       # cấu hình ruff / black / mypy / pytest / coverage
└── requirements.txt
```

`app/config.py` giai quyet duong dan tuong doi theo `BACKEND_DIR` (chinh la thu muc nay),
nen `data/`, `database/`, `DataTuVietTat_and_TuDienTiengViet/` phai o cung cap voi `app/`.
File `.env` duoc tim theo thu tu `backend/.env` roi `<repo-root>/.env`.

## Lenh thuong dung

Chay tu **thu muc `backend/`**:

```powershell
..\.venv\Scripts\python.exe -m pytest tests -q
..\.venv\Scripts\python.exe -m pytest tests --cov=app --cov-report=term-missing:skip-covered -q
..\.venv\Scripts\python.exe -m ruff check app tests scripts database
..\.venv\Scripts\python.exe -m mypy
..\.venv\Scripts\python.exe -m bandit -r app scripts -q
```

Chay server dev (tu repo root):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_demo_servers.ps1
# hoac chi backend
scripts\run_backend_dev.cmd
```

Khoi tao schema:

```powershell
sqlcmd -S "<SERVER>\SQLEXPRESS" -d VietNormalizer -E -I -i backend\database\init_schema.sql
```
