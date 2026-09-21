# SQL Server Setup

## 1. Cai dat
- Cai `SQL Server Express`.
- Cai `SQL Server Management Studio (SSMS)`.
- Cai `ODBC Driver 18 for SQL Server`.

## 2. Tao database
- Mo SSMS va ket noi vao `localhost\\SQLEXPRESS`.
- Tao database `VietNormalizer`.

```sql
CREATE DATABASE VietNormalizer;
GO
```

## 3. Tao SQL login cho che do SQLEXPRESS
```sql
USE master;
GO
CREATE LOGIN normalizer_app WITH PASSWORD = '123456aA@';
GO
USE VietNormalizer;
GO
CREATE USER normalizer_app FOR LOGIN normalizer_app;
GO
ALTER ROLE db_owner ADD MEMBER normalizer_app;
GO
```

## 4. Khoi tao schema
- Mo file `backend/database/init_schema.sql` trong SSMS.
- Chon database `VietNormalizer`.
- Run toan bo script.

Hoac chay bang `sqlcmd` tu thu muc project.

LocalDB:

```powershell
sqlcmd -S "(localdb)\MSSQLLocalDB" -d VietNormalizer -E -I -i backend\database\init_schema.sql
```

SQLEXPRESS:

```powershell
sqlcmd -S "localhost\SQLEXPRESS" -d VietNormalizer -U normalizer_app -P "123456aA@" -I -i backend\database\init_schema.sql
```

Neu gap loi `CREATE INDEX failed` lien quan `QUOTED_IDENTIFIER`, hay cap nhat file
`backend/database/init_schema.sql` moi nhat va chay lai lenh co tham so `-I`.

## 5. Chon cach ket noi

### SQLEXPRESS
Su dung `.env`:

```env
SQL_MODE=sqlexpress
SQL_HOST=localhost
SQL_INSTANCE=SQLEXPRESS
SQL_DATABASE=VietNormalizer
SQL_AUTH=sql
SQL_USERNAME=normalizer_app
SQL_PASSWORD=123456aA@
SQL_ENCRYPT=no
SQL_TRUST_SERVER_CERTIFICATE=yes
```

Neu dang ket noi bang Windows Authentication nhu SSMS:

```env
SQL_MODE=sqlexpress
SQL_HOST=<TEN-MAY-CUA-BAN>
SQL_INSTANCE=SQLEXPRESS
SQL_DATABASE=VietNormalizer
SQL_AUTH=windows
SQL_ENCRYPT=yes
SQL_TRUST_SERVER_CERTIFICATE=yes
```

### LocalDB
Su dung `.env`:

```env
SQL_MODE=localdb
SQL_INSTANCE=MSSQLLocalDB
SQL_DATABASE=VietNormalizer
SQL_AUTH=windows
SQL_ENCRYPT=no
SQL_TRUST_SERVER_CERTIFICATE=yes
```

Luu y:
- `SQL_MODE` chi nhan `sqlexpress` hoac `localdb`.
- Neu can dung ten may/host rieng, dat vao `SQL_HOST`, vi du `SQL_HOST=<TEN-MAY-CUA-BAN>`; khong dat ten may vao `SQL_MODE`.
- Dat `SQL_AUTH=windows` khi SQL Server dung Windows Authentication va khong co mat khau.
- Dat `SQL_AUTH=sql` khi dung SQL login `SQL_USERNAME`/`SQL_PASSWORD`.
- Voi ODBC Driver 18 tren may dev, dat `SQL_ENCRYPT=no` neu gap loi `Encryption not supported on the client`.

## 5b. Tai khoan demo (CHI cho may dev/demo)

`init_schema.sql` chi tao schema va 2 role co dinh. No KHONG tao tai khoan nao.

Neu can tai khoan demo de thu UI, chay them script rieng:

```powershell
sqlcmd -S "localhost\SQLEXPRESS" -d VietNormalizer -E -I -i backend\database\seed_demo.sql
```

Mat khau cua cac tai khoan nay duoc ghi ngay trong `backend/database/seed_demo.sql`
va da cong bo trong repo, nen **khong chay script nay tren moi truong ma nguoi khac
truy cap duoc**. Tat chung khi khong con can:

```sql
UPDATE dbo.users SET is_active = 0
WHERE username IN (N'admin_main', N'demo_user_01', N'demo_user_02');
```

## 6. Seed du lieu
- Sau khi schema san sang, chay `backend/database/seed_from_json.py`.
- Script se import `teencode.json` va cac bo tu dien `Viet11K/22K/39K/74K` vao SQL Server.

## 7. Kiem tra truoc demo
- Dam bao SQL Server service dang chay.
- Kiem tra file `.env`.
- Neu DB chua san sang, CLI van co the doc approved JSON o che do fallback, nhung pending/history se khong duoc ghi.

Lenh kiem tra nhanh tren Windows:

```powershell
sc.exe query MSSQL$SQLEXPRESS
cd backend
..\.venv\Scripts\python.exe -c "from app.config import get_settings; from app.data_manager.db import health_check; print(health_check(get_settings()))"
```

Neu `sc.exe` bao service khong ton tai, may chua cai SQL Server Express instance `SQLEXPRESS`
hoac dang dung ten instance khac. Cai SQL Server Express hoac sua `SQL_INSTANCE` trong `.env`.
