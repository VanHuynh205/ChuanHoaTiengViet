"""Subprocess fixture: real API/auth/cache, isolated SQLite-backed test repository."""
import json
import sqlite3
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_api import ApiTests
from app.api.dependencies import get_current_user
from app.data_manager.pending_service import PendingAbbreviationService
import app.api.routes as routes


class Repository:
    def __init__(self, directory):
        self.path = directory / "source.sqlite3"
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT OR IGNORE INTO records VALUES (1, 'đăng ký')")

    def list_approved_abbreviations(self):
        with sqlite3.connect(self.path) as conn:
            meaning = conn.execute("SELECT value FROM records WHERE id=1").fetchone()[0]
        return [{"id": "1", "abbr": "dk", "expanded": meaning,
                 "alternative_expansions": [], "domain": "general", "source": "test"}]

    def get_dictionary_words(self):
        return {"hôm", "nay", "học", "phần"}

    def get_approved_abbreviation_details(self, *args, **kwargs):
        return self.list_approved_abbreviations()[0]

    def bulk_upsert_abbreviations(self, rows, **kwargs):
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE records SET value=? WHERE id=1", (rows[0]["expanded"],))

    def submit_pending_abbreviation(self, **kwargs):
        return {"status": "IGNORED", "pending_id": None}


def main():
    directory = Path(sys.argv[1])
    fixture = ApiTests()
    fixture.setUp()
    fixture.settings = replace(fixture.settings, data_dir=directory,
                               ai_disable_network=True, diacritic_auto_detect=False,
                               live_incremental_min_chars=1, live_incremental_chunk_words=5)
    service = PendingAbbreviationService(fixture.settings)
    service.repository = Repository(directory)
    service.db_is_ready = lambda: True
    service.phrase_override_repository = SimpleNamespace(is_ready=lambda: False)
    fixture.pending_service = service
    routes.UsageStatsRepository = lambda settings: SimpleNamespace(record_usage_bulk=lambda *a, **k: None)
    del fixture.app.dependency_overrides[get_current_user]
    user_token = fixture._issue_token("user-1")
    admin_token = fixture._issue_token("admin-1")
    for line in sys.stdin:
        command = json.loads(line)
        if command["op"] == "read":
            response = fixture.client.post("/api/normalize/live",
                headers={"Authorization": "Bearer " + user_token},
                json={"text": "hôm nay dk học phần.\nhôm nay dk học phần.", "allowAI": False})
        elif command["op"] == "save":
            if command.get("fail_export"):
                def fail(*args):
                    raise OSError("synthetic export failure")
                service.json_store.export_approved_abbreviations = fail
            response = fixture.client.put("/api/abbreviations/dk",
                headers={"Authorization": "Bearer " + admin_token},
                json={"expanded": command["meaning"], "alternative_expansions": [], "domain": "general"})
        else:
            response = fixture.client.get("/api/admin/dictionary/sync-status",
                headers={"Authorization": "Bearer " + admin_token})
        print(json.dumps({"status": response.status_code, "body": response.json()}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
