import datetime as dt

import pytest

from app.config import Settings
from app.data_manager.history_repo import HistoryRepository
from app.data_manager.new_tables_repo import (
    PhraseOverrideRepository,
    PreferencesRepository,
    SessionRepository,
    UsageStatsRepository,
    _hash_token,
)
from app.data_manager.user_repo import UserRepository


class _FakeResult:
    def __init__(self, rows=None, scalar_value=None, rowcount=1):
        self._rows = list(rows or [])
        self._scalar_value = scalar_value
        self.rowcount = rowcount

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows

    def scalar(self):
        return self._scalar_value


class _FakeSession:
    def __init__(self, results):
        self._results = list(results)
        self.calls = []
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params or {}))
        if not self._results:
            return _FakeResult()
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        if callable(result):
            return result(statement, params or {})
        return result

    def commit(self):
        self.commits += 1


def _repository(repository_cls, results):
    session = _FakeSession(results)
    repository = object.__new__(repository_cls)
    repository.settings = Settings()
    repository.session_factory = lambda: session
    return repository, session


def _user_row(**overrides):
    row = {
        "id": "user-1",
        "username": "demo",
        "email": "demo@example.com",
        "password_hash": "hash-1",
        "is_active": 1,
        "created_at": dt.datetime(2026, 5, 1, tzinfo=dt.timezone.utc),
        "updated_at": dt.datetime(2026, 5, 2, tzinfo=dt.timezone.utc),
        "roles_csv": "user",
    }
    row.update(overrides)
    return row


def _history_row(**overrides):
    row = {
        "id": "history-1",
        "input_text": "dk hp",
        "output_text": "dang ky hoc phan",
        "error_types_json": '["ABBREVIATION"]',
        "model_used": None,
        "from_cache": 0,
        "latency_ms": 12.5,
        "domain": "general",
        "source_kind": "web_live",
        "user_id": "user-1",
        "username_snapshot": "demo",
        "created_at": dt.datetime(2026, 5, 1, tzinfo=dt.timezone.utc),
    }
    row.update(overrides)
    return row


def test_user_repository_auth_create_role_and_delete_paths():
    repository, session = _repository(
        UserRepository,
        [
            _FakeResult(rows=[_user_row()]),
            _FakeResult(),
            _FakeResult(),
            _FakeResult(rows=[_user_row(username="new_user", email="new@example.com")]),
            _FakeResult(rows=[_user_row(), _user_row(id="admin-1", username="admin")]),
            _FakeResult(),
            _FakeResult(),
            _FakeResult(rows=[_user_row(roles_csv="admin")]),
            _FakeResult(rows=[_user_row()]),
            _FakeResult(),
            _FakeResult(),
            _FakeResult(),
            _FakeResult(),
            _FakeResult(),
        ],
    )

    user, password_hash = repository.find_for_authentication("demo")
    assert password_hash == "hash-1"
    assert user["roles"] == ["user"]
    assert user["created_at"].startswith("2026-05-01")

    created = repository.create_user(
        username="new_user",
        email="new@example.com",
        password_hash="hash-new",
    )
    assert created["username"] == "new_user"

    assert [user["id"] for user in repository.list_users()] == ["user-1", "admin-1"]
    assigned = repository.assign_role("user-1", role_name="admin", assigned_by="admin")
    assert assigned["roles"] == ["admin"]

    deleted = repository.delete_user("user-1")
    assert deleted["id"] == "user-1"
    assert session.commits == 3


def test_user_repository_rejects_invalid_delete_and_blank_hash():
    repository, _session = _repository(UserRepository, [_FakeResult(rows=[])])

    with pytest.raises(ValueError, match="new_hash"):
        repository.update_password_hash("user-1", "")
    with pytest.raises(ValueError, match="USER_NOT_FOUND"):
        repository.delete_user("missing-user")

    admin_repository, _admin_session = _repository(
        UserRepository,
        [_FakeResult(rows=[_user_row(roles_csv="admin")])],
    )
    with pytest.raises(ValueError, match="ADMIN_USER_DELETE_FORBIDDEN"):
        admin_repository.delete_user("admin-1")


def test_history_repository_logs_lists_deletes_and_normalizes_rows():
    repository, session = _repository(
        HistoryRepository,
        [
            _FakeResult(),
            _FakeResult(
                rows=[
                    _history_row(),
                    _history_row(error_types_json="not-json", from_cache=1),
                ]
            ),
            _FakeResult(rows=[_history_row(id="history-delete")]),
            _FakeResult(),
            _FakeResult(),
        ],
    )

    created = repository.log_normalization(
        input_text="dk hp",
        output_text="dang ky hoc phan",
        error_types=["ABBREVIATION"],
        from_cache=True,
        latency_ms=9.5,
        user_id="user-1",
        username_snapshot="demo",
    )
    assert created is not None
    assert created["from_cache"] is True
    assert session.calls[0][1]["error_types_json"] == '["ABBREVIATION"]'

    user_history = repository.list_history(user_id="user-1", limit=500)
    assert user_history[0]["error_types"] == ["ABBREVIATION"]
    assert session.calls[1][1]["user_id"] == "user-1"

    deleted = repository.delete_history_entry("history-delete", user_id="user-1")
    assert deleted["id"] == "history-delete"
    repository.log_error("api", "boom", stack_trace="trace", payload_json="{}")
    assert session.commits == 3


def test_history_repository_delete_missing_raises_not_found():
    repository, _session = _repository(HistoryRepository, [_FakeResult(rows=[])])

    with pytest.raises(ValueError, match="HISTORY_NOT_FOUND"):
        repository.delete_history_entry("missing-history", user_id="user-1")


def test_history_repository_requires_an_owner_for_reads_and_deletes():
    repository, _session = _repository(HistoryRepository, [])

    with pytest.raises(ValueError, match="HISTORY_OWNER_REQUIRED"):
        repository.list_history(user_id="")
    with pytest.raises(ValueError, match="HISTORY_OWNER_REQUIRED"):
        repository.delete_history_entry("history-1", user_id="")


def test_session_repository_full_lifecycle_paths():
    # Only ONE OBJECT_ID probe: the table-existence answer is cached per session
    # factory, so authenticated requests no longer pay a round-trip per call.
    repository, session = _repository(
        SessionRepository,
        [
            _FakeResult(scalar_value=1),
            _FakeResult(rows=[{"id": "session-1", "user_id": "user-1", "is_active": 1}]),
            _FakeResult(scalar_value=1),
            _FakeResult(rowcount=1),
            _FakeResult(rowcount=2),
            _FakeResult(rows=[{"id": "session-1", "ip_address": "127.0.0.1"}]),
            _FakeResult(rowcount=3),
        ],
    )

    created = repository.create_session(
        user_id="user-1",
        token="raw-token",
        expires_at="2026-05-28T00:00:00",
        user_agent="browser",
    )
    assert created["id"] == "session-1"
    assert session.calls[1][1]["token_hash"] == _hash_token("raw-token")
    assert session.calls[1][1]["token_hash"] != "raw-token"

    assert repository.is_token_valid("raw-token") is True
    assert repository.revoke_token("raw-token", reason="logout") is True
    assert repository.revoke_all_user_sessions("user-1", reason="admin") == 2
    assert repository.get_active_sessions("user-1")[0]["id"] == "session-1"
    assert repository.cleanup_expired() == 3


def test_session_repository_allows_only_when_session_table_was_never_deployed():
    """Missing table => allow (nothing was ever revoked). DB failure => reject.

    The two cases used to be conflated, which meant an unhealthy database
    silently re-enabled every revoked token.
    """
    missing_table_repo, _missing_session = _repository(
        SessionRepository,
        [_FakeResult(scalar_value=None)],
    )
    assert missing_table_repo.is_token_valid("token") is True

    probe_failure_repo, _probe_session = _repository(
        SessionRepository,
        [RuntimeError("db down")],
    )
    assert probe_failure_repo.is_token_valid("token") is False

    query_failure_repo, _query_session = _repository(
        SessionRepository,
        [_FakeResult(scalar_value=1), RuntimeError("db down")],
    )
    assert query_failure_repo.is_token_valid("token") is False


def test_session_repository_bulk_usage_and_hashing_ignores_surrounding_whitespace():
    assert _hash_token(" raw-token ") == _hash_token("raw-token")


def test_preferences_repository_read_write_delete_paths():
    repository, session = _repository(
        PreferencesRepository,
        [
            _FakeResult(scalar_value=1),
            _FakeResult(rows=[{"preference_key": "theme", "preference_value": "dark"}]),
            _FakeResult(scalar_value="dark"),
            _FakeResult(rowcount=1),
            _FakeResult(rowcount=1),
        ],
    )

    assert repository.is_ready() is True
    assert repository.get_all("user-1", category="ui")[0]["preference_key"] == "theme"
    assert repository.get("user-1", "theme") == "dark"
    assert repository.set("user-1", "theme", "light", category="ui") is True
    assert repository.delete("user-1", "theme") is True
    assert session.commits == 2


def test_phrase_override_repository_crud_and_dict_paths():
    repository, session = _repository(
        PhraseOverrideRepository,
        [
            _FakeResult(scalar_value=1),
            _FakeResult(rows=[{"id": "po-1", "phrase_key": "dk hp", "phrase_value": "dang ky"}]),
            _FakeResult(
                rows=[{"id": "po-2", "phrase_key": "hoc phi", "phrase_value": "học phí"}]
            ),
            _FakeResult(rows=[{"id": "po-3", "phrase_key": "cty", "phrase_value": "cong ty"}]),
            _FakeResult(rowcount=1),
            _FakeResult(rowcount=1),
            _FakeResult(rows=[{"phrase_key": "dk hp", "phrase_value": "dang ky hoc phan"}]),
        ],
    )

    assert repository.is_ready() is True
    assert repository.get_active()[0]["id"] == "po-1"
    assert repository.get_active(domain="school")[0]["phrase_key"] == "hoc phi"
    assert repository.create("cty", "cong ty", created_by="admin")["id"] == "po-3"
    assert repository.update("po-3", phrase_value="công ty", priority=10, notes="ok") is True
    assert repository.soft_delete("po-3", updated_by="admin") is True
    assert repository.as_dict(domain="general") == {"dk hp": "dang ky hoc phan"}
    assert session.commits == 3


def test_usage_stats_repository_records_and_queries_paths():
    repository, session = _repository(
        UsageStatsRepository,
        [
            _FakeResult(scalar_value=1),
            _FakeResult(rowcount=1),
            _FakeResult(rows=[{"abbr": "dk", "expanded_chosen": "dang ky", "total_count": 3}]),
            _FakeResult(rows=[{"usage_date": "2026-05-28", "total_uses": 5}]),
        ],
    )

    assert repository.is_ready() is True
    assert repository.record_usage(
        "dk" * 100,
        "dang ky" * 100,
        source_kind="live" * 20,
    )
    params = session.calls[1][1]
    assert len(params["abbr"]) == 100
    assert len(params["expanded_chosen"]) == 500
    assert len(params["source_kind"]) == 50
    assert repository.get_top_abbreviations(days=30, limit=10)[0]["abbr"] == "dk"
    assert repository.get_daily_stats(days=7)[0]["total_uses"] == 5


def test_usage_stats_record_usage_failure_is_non_critical():
    repository, _session = _repository(UsageStatsRepository, [RuntimeError("db down")])

    assert repository.record_usage("dk", "dang ky") is False
