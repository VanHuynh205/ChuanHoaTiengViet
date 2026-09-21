"""Read SQL metadata without exposing connection strings or user records."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import get_settings
from app.data_manager.db import build_odbc_connection_string
import pyodbc

settings = get_settings()
report = {"sql_mode": settings.sql_mode, "sql_auth": settings.sql_auth}
queries = {
    "tables": "SELECT name FROM sys.tables WHERE schema_id = SCHEMA_ID('dbo') ORDER BY name",
    "columns": "SELECT t.name, c.name, TYPE_NAME(c.user_type_id), c.max_length, c.is_nullable FROM sys.tables t JOIN sys.columns c ON t.object_id=c.object_id WHERE t.schema_id=SCHEMA_ID('dbo') ORDER BY t.name,c.column_id",
    "cleanup_procedure": "SELECT name FROM sys.procedures WHERE name='sp_cleanup_expired_data'",
    "backup_summary": "SELECT type, MAX(backup_finish_date) FROM msdb.dbo.backupset WHERE database_name=DB_NAME() GROUP BY type",
    "restore_summary": "SELECT MAX(restore_date) FROM msdb.dbo.restorehistory WHERE destination_database_name=DB_NAME()",
    "agent_jobs": "SELECT COUNT(*) FROM msdb.dbo.sysjobs",
}
try:
    connection = pyodbc.connect(build_odbc_connection_string(settings), timeout=5, autocommit=False)
except Exception as exc:
    report["connection"] = {"error_type": type(exc).__name__, "sqlstate": str(exc.args[0])[:5]}
else:
    report["connection"] = "connected"
    connection.timeout = 5
    for name, sql in queries.items():
        try:
            report[name] = [list(row) for row in connection.cursor().execute(sql).fetchall()]
        except Exception as exc:
            report[name] = {"error_type": type(exc).__name__, "sqlstate": str(exc.args[0])[:5]}
    connection.rollback()
    connection.close()
    declared = sorted(set(re.findall(r"CREATE TABLE\s+(?:dbo\.)?\[?(\w+)", (ROOT / "backend/database/init_schema.sql").read_text(encoding="utf-8"), re.I)))
    observed = {row[0] for row in report.get("tables", [])}
    report["declared_tables"] = declared
    report["missing_declared_tables"] = sorted(set(declared) - observed)
print(json.dumps(report, ensure_ascii=True, default=str, indent=2))
