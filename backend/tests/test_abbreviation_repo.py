import json
import unittest

from app.config import Settings
from app.data_manager.abbreviation_repo import AbbreviationRepository


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class _TableMissingSession:
    def __init__(self):
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None):
        self.executed.append((str(query), params))
        return _ScalarResult(0)


class _InvalidObjectSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params=None):
        raise RuntimeError(
            "[42S02] [Microsoft][ODBC Driver 18 for SQL Server][SQL Server]"
            "Invalid object name 'dbo.user_abbreviation_overrides'."
        )


class AbbreviationRepositoryHelpersTests(unittest.TestCase):
    def setUp(self):
        AbbreviationRepository._schema_table_cache.clear()

    def _build_repository(self, settings, session):
        repository = object.__new__(AbbreviationRepository)
        repository.settings = settings
        repository.session_factory = lambda: session
        return repository

    def test_deserialize_meanings_returns_unique_trimmed_values(self):
        result = AbbreviationRepository._deserialize_meanings(
            '["  điều kiện  ", "", "điều kiện", "điều khoản"]'
        )

        self.assertEqual(result, ["điều kiện", "điều khoản"])

    def test_merge_additional_meanings_preserves_existing_primary_and_appends_new_meanings(self):
        result = AbbreviationRepository._merge_additional_meanings(
            primary="điều kiện",
            existing=["điều khoản"],
            candidates=["điều kiện", "điều kiện khác", "điều khoản"],
        )

        self.assertEqual(result, ["điều khoản", "điều kiện khác"])

    def test_list_user_overrides_returns_empty_when_table_is_missing(self):
        session = _TableMissingSession()
        repository = self._build_repository(
            Settings(sql_database="test_missing_user_overrides"),
            session,
        )

        result = repository.list_user_abbreviation_overrides(
            user_id="169E5D58-D8A3-4E7D-B132-10CDCD51D305"
        )

        self.assertEqual(result, [])
        self.assertEqual(len(session.executed), 1)
        self.assertIn("OBJECT_ID", session.executed[0][0])

    def test_list_user_overrides_handles_stale_schema_cache(self):
        repository = self._build_repository(
            Settings(sql_database="test_stale_user_overrides_cache"),
            _InvalidObjectSession(),
        )
        repository._set_table_exists(repository._USER_OVERRIDE_TABLE, True)

        result = repository.list_user_abbreviation_overrides(
            user_id="169E5D58-D8A3-4E7D-B132-10CDCD51D305"
        )

        self.assertEqual(result, [])
        self.assertFalse(repository._table_exists(repository._USER_OVERRIDE_TABLE))

    def test_upsert_user_override_reports_missing_schema_when_table_is_missing(self):
        session = _TableMissingSession()
        repository = self._build_repository(
            Settings(sql_database="test_missing_user_override_upsert"),
            session,
        )

        result = repository.upsert_user_abbreviation_override(
            user_id="169E5D58-D8A3-4E7D-B132-10CDCD51D305",
            abbr="dk",
            meaning="dang ky",
        )

        self.assertEqual(result["status"], "DB_SCHEMA_MISSING")
        self.assertEqual(result["abbr"], "dk")
        self.assertEqual(result["expanded"], "dang ky")


if __name__ == "__main__":
    unittest.main()


def test_seeding_merges_alternatives_instead_of_erasing_approved_meanings():
    """Re-running the documented seed step must not delete curated meanings.

    ``bulk_upsert_abbreviations`` used to write the seed file's alternatives
    verbatim, so an admin-approved extra meaning vanished the next time
    ``database/seed_from_json.py`` ran.
    """
    updates = []

    class _Result:
        def __init__(self, row=None):
            self._row = row

        def mappings(self):
            return self

        def first(self):
            return self._row

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, statement, params=None):
            sql = str(statement)
            if "SELECT" in sql and "alternative_expansions_json" in sql:
                return _Result(
                    {
                        "id": "abbr-1",
                        "alternative_expansions_json": '["dang ky hoc phan"]',
                    }
                )
            updates.append((sql, params))
            return _Result()

        def commit(self):
            pass

    repository = object.__new__(AbbreviationRepository)
    repository.settings = Settings()
    repository.session_factory = lambda: _Session()

    repository.bulk_upsert_abbreviations(
        [{"abbr": "dk", "expanded": "dang ky", "alternative_expansions": ["duoc khong"]}]
    )

    stored = json.loads(updates[-1][1]["alternative_expansions_json"])
    assert "dang ky hoc phan" in stored, stored
    assert "duoc khong" in stored, stored

    updates.clear()
    repository.bulk_upsert_abbreviations(
        [{"abbr": "dk", "expanded": "dang ky", "alternative_expansions": ["duoc khong"]}],
        replace_alternatives=True,
    )
    stored = json.loads(updates[-1][1]["alternative_expansions_json"])
    assert stored == ["duoc khong"], stored


def test_seed_does_not_replace_admin_primary_or_reintroduce_removed_alternatives():
    from unittest.mock import MagicMock
    session = MagicMock()
    session.__enter__.return_value = session
    session.execute.return_value.mappings.return_value.first.return_value = {
        "id": "abbr-1", "approved_by": "admin_main",
        "alternative_expansions_json": "[]",
    }
    repository = object.__new__(AbbreviationRepository)
    repository.settings = Settings()
    repository.session_factory = lambda: session
    repository.bulk_upsert_abbreviations([
        {"abbr": "dk", "expanded": "old primary", "alternative_expansions": ["removed meaning"]}
    ])
    assert session.execute.call_count == 1  # Only inspect; no UPDATE of curated record.
