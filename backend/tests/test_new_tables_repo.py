import logging

from app.data_manager.new_tables_repo import SessionRepository


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeSession:
    def __init__(self, object_id=None):
        self.object_id = object_id
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append(sql)
        if "OBJECT_ID" in sql:
            return _ScalarResult(self.object_id)
        if "dbo.user_sessions" in sql:
            raise AssertionError("user_sessions query should be skipped when the table is missing")
        return _ScalarResult(None)


class _FakeSessionFactory:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self.session


def test_create_session_skips_missing_user_sessions_table(caplog):
    session = _FakeSession(object_id=None)
    repo = SessionRepository.__new__(SessionRepository)
    repo.session_factory = _FakeSessionFactory(session)

    with caplog.at_level(logging.WARNING):
        result = repo.create_session(
            user_id="user-1",
            token="token-1",
            expires_at="2026-05-24T00:00:00",
        )

    assert result is None
    assert len(session.statements) == 1
    assert "OBJECT_ID" in session.statements[0]
    assert "Failed to create user session" not in caplog.text
