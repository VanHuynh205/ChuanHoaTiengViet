"""Isolated browser acceptance fixture for dictionary consistency (no operational SQL)."""
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_api import ApiTests
from dictionary_worker import Repository
from app.api.dependencies import get_current_user
from app.data_manager.pending_service import PendingAbbreviationService
import app.api.routes as routes


def create_fixture():
    fixture = ApiTests()
    fixture.setUp()
    directory = tempfile.TemporaryDirectory(prefix="dictionary-e2e-")
    fixture.settings = replace(fixture.settings, data_dir=Path(directory.name),
        ai_disable_network=True, diacritic_auto_detect=False)
    service = PendingAbbreviationService(fixture.settings)
    service.repository = Repository(Path(directory.name))
    service.db_is_ready = lambda: True
    service.phrase_override_repository = SimpleNamespace(is_ready=lambda: False)
    fixture.pending_service = service
    del fixture.app.dependency_overrides[get_current_user]
    routes.UsageStatsRepository = lambda settings: SimpleNamespace(record_usage_bulk=lambda *a, **k: None)
    original_export = service.json_store.export_approved_abbreviations

    @fixture.app.get("/__test/session")
    def session(admin: bool = False):
        user_id = "admin-1" if admin else "user-1"
        return {"token": fixture._issue_token(user_id), "user": fixture.user_repository.users[user_id]}

    @fixture.app.post("/__test/export-failure")
    def export_failure(enabled: bool = True):
        def fail(*args):
            raise OSError("synthetic export failure")
        service.json_store.export_approved_abbreviations = fail if enabled else original_export
        return {"enabled": enabled}

    fixture.app.state.fixture_directory = directory
    return fixture.app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_fixture(), host="127.0.0.1", port=8018)
