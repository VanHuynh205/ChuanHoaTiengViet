import json
import tempfile
from pathlib import Path

from app.config import Settings
from app.data_manager.json_sync import JsonDataStore
from app.data_manager.pending_service import PendingAbbreviationService


def test_json_export_includes_primary_and_alternative_meanings(tmp_path):
    (tmp_path / "abbreviations").mkdir(parents=True, exist_ok=True)
    settings = Settings(data_dir=tmp_path)
    store = JsonDataStore(settings)

    target = store.export_approved_abbreviations(
        [
            {
                "id": "1",
                "abbr": "sp",
                "expanded": "san pham",
                "domain": "general",
                "source": "sql_server",
                "created_at": "2025-01-01T00:00:00",
                "approved_by": "admin",
                "alternative_expansions": ["sản phẩm", "service pack"],
            }
        ]
    )

    with target.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    assert payload["abbreviations"][0]["abbr"] == "sp"
    assert payload["abbreviations"][0]["expanded"] == "san pham"
    assert payload["abbreviations"][0]["alternative_expansions"] == ["sản phẩm", "service pack"]


def test_json_export_does_not_replace_seed_abbreviation_records(tmp_path):
    (tmp_path / "abbreviations").mkdir(parents=True, exist_ok=True)
    with (tmp_path / "abbreviations" / "teencode.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {"abbreviations": [{"id": "seed-1", "abbr": "dk", "expanded": "đăng ký"}]},
            handle,
            ensure_ascii=False,
        )

    settings = Settings(data_dir=tmp_path)
    store = JsonDataStore(settings)

    store.export_approved_abbreviations(
        [
            {
                "id": "sql-1",
                "abbr": "nv",
                "expanded": "nhân viên",
                "domain": "general",
                "source": "sql_server",
                "created_at": "2026-06-06T00:00:00",
                "approved_by": "admin",
                "alternative_expansions": [],
            }
        ]
    )

    records = store.load_abbreviation_records()

    assert {record["abbr"] for record in records} == {"dk", "nv"}


def test_submit_pending_still_creates_pending_when_word_exists_in_json(tmp_path):
    (tmp_path / "abbreviations").mkdir(parents=True, exist_ok=True)
    with (tmp_path / "abbreviations" / "teencode.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {"abbreviations": [{"id": "1", "abbr": "ko", "expanded": "khong"}]},
            handle,
            ensure_ascii=False,
        )
    settings = Settings(data_dir=tmp_path)
    service = PendingAbbreviationService(settings)

    captured = {}

    class FakeRepository:
        def submit_pending_abbreviation(self, **kwargs):
            captured.update(kwargs)
            return {
                "abbr": kwargs["abbr"],
                "status": "PENDING_CREATED",
                "pending_id": "pending-ko",
                "has_suggested": False,
            }

    service.repository = FakeRepository()

    result = service.submit_pending_abbreviation("ko", submitted_by="tester")

    assert result["status"] == "PENDING_CREATED"
    assert captured["abbr"] == "ko"
    assert captured["submitted_by"] == "tester"


def test_capture_pending_suggestion_trims_and_delegates_to_repository(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = PendingAbbreviationService(settings)

    captured = {}

    class FakeRepository:
        def capture_pending_suggestion(self, pending_id, suggested, submitted_by=None):
            captured["pending_id"] = pending_id
            captured["suggested"] = suggested
            captured["submitted_by"] = submitted_by
            return {"pending_id": pending_id, "status": "SUGGESTION_CAPTURED"}

    service.repository = FakeRepository()

    result = service.capture_pending_suggestion("pending-1", "  điều kiện  ", submitted_by="tester")

    assert result["status"] == "SUGGESTION_CAPTURED"
    assert captured["pending_id"] == "pending-1"
    assert captured["suggested"] == "điều kiện"
    assert captured["submitted_by"] == "tester"


def test_capture_pending_suggestion_ignores_blank_meaning(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = PendingAbbreviationService(settings)

    class FakeRepository:
        def capture_pending_suggestion(self, pending_id, suggested, submitted_by=None):
            raise AssertionError("Repository should not be called for blank suggestion")

    service.repository = FakeRepository()

    result = service.capture_pending_suggestion("pending-1", "   ", submitted_by="tester")

    assert result["status"] == "IGNORED"


def test_get_approved_abbreviations_merges_json_bootstrap_with_db_results(tmp_path):
    (tmp_path / "abbreviations").mkdir(parents=True, exist_ok=True)
    with (tmp_path / "abbreviations" / "bootstrap_overrides.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(
            {
                "abbreviations": [
                    {"abbr": "nt", "expanded": "nhắn tin"},
                    {"abbr": "ko", "expanded": "không"},
                ]
            },
            handle,
            ensure_ascii=False,
        )

    settings = Settings(data_dir=tmp_path)
    service = PendingAbbreviationService(settings)

    class FakeRepository:
        def is_ready(self):
            return True

        def get_approved_abbreviation_map(self):
            return {"ko": "khong", "r": "roi"}

    service.repository = FakeRepository()
    service.db_is_ready = lambda: True  # type: ignore[method-assign]

    result = service.get_approved_abbreviations()

    assert result["nt"] == "nhắn tin"
    assert result["ko"] == "khong"
    assert result["r"] == "roi"


def test_list_approved_abbreviations_uses_json_seed_when_db_unavailable(tmp_path):
    (tmp_path / "abbreviations").mkdir(parents=True, exist_ok=True)
    with (tmp_path / "abbreviations" / "teencode.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(
            {
                "abbreviations": [
                    {
                        "abbr": "dk",
                        "expanded": "dang ky",
                        "alternative_expansions": ["dung khong"],
                        "domain": "general",
                    },
                    {
                        "abbr": "vc",
                        "expanded": "viec",
                        "alternative_expansions": ["vo chong"],
                        "domain": "text_normalization",
                    },
                ]
            },
            handle,
            ensure_ascii=False,
        )

    service = PendingAbbreviationService(Settings(data_dir=tmp_path))
    service.db_is_ready = lambda: False  # type: ignore[method-assign]

    result = service.list_approved_abbreviations()

    assert {(record["abbr"], record["domain"]) for record in result} == {
        ("dk", "general"),
        ("vc", "text_normalization"),
    }
    assert result[0]["id"]
    assert result[0]["alternative_expansions"]


def test_list_approved_abbreviations_returns_all_domains_by_default(tmp_path):
    (tmp_path / "abbreviations").mkdir(parents=True, exist_ok=True)
    with (tmp_path / "abbreviations" / "teencode.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(
            {
                "abbreviations": [
                    {
                        "abbr": "nt",
                        "expanded": "nhan tin",
                        "domain": "text_normalization",
                    }
                ]
            },
            handle,
            ensure_ascii=False,
        )

    service = PendingAbbreviationService(Settings(data_dir=tmp_path))

    class FakeRepository:
        def list_approved_abbreviations(self):
            return [
                {
                    "id": "abbr-dk",
                    "abbr": "dk",
                    "expanded": "dang ky",
                    "alternative_expansions": ["dung khong"],
                    "domain": "general",
                    "source": "sql_server",
                    "created_at": None,
                    "approved_by": "admin",
                }
            ]

    service.repository = FakeRepository()
    service.db_is_ready = lambda: True  # type: ignore[method-assign]

    all_records = service.list_approved_abbreviations()
    general_records = service.list_approved_abbreviations(domain="general")

    assert {(record["abbr"], record["domain"]) for record in all_records} == {
        ("dk", "general"),
        ("nt", "text_normalization"),
    }
    assert [record["abbr"] for record in general_records] == ["dk"]


def test_live_normalization_data_loads_db_records_once(tmp_path):
    PendingAbbreviationService.invalidate_live_normalization_cache()
    settings = Settings(data_dir=tmp_path)
    service = PendingAbbreviationService(settings)

    class FakeJsonStore:
        def load_abbreviations(self):
            return {"nt": "nhan tin"}

        def load_dictionary_words(self):
            return {"fallback"}

        def load_phrase_overrides(self):
            return {}

        def load_mined_phrases(self):
            return {}

    class FakeRepository:
        def __init__(self):
            self.list_approved_calls = 0
            self.dictionary_calls = 0

        def list_approved_abbreviations(self):
            self.list_approved_calls += 1
            return [
                {
                    "abbr": "ko",
                    "expanded": "khong",
                    "alternative_expansions": [],
                    "domain": "general",
                },
                {
                    "abbr": "yt",
                    "expanded": "y te",
                    "alternative_expansions": [],
                    "domain": "medical",
                },
            ]

        def get_dictionary_words(self):
            self.dictionary_calls += 1
            return {"hom", "nay"}

    readiness_checks = {"count": 0}
    repository = FakeRepository()
    service.json_store = FakeJsonStore()
    service.repository = repository

    def db_is_ready():
        readiness_checks["count"] += 1
        return True

    service.db_is_ready = db_is_ready  # type: ignore[method-assign]

    result = service.get_live_normalization_data(domain="general")
    cached_result = service.get_live_normalization_data(domain="general")

    assert readiness_checks["count"] == 1
    assert repository.list_approved_calls == 1
    assert repository.dictionary_calls == 1
    assert cached_result is result
    assert result.abbreviations == {"nt": "nhan tin", "ko": "khong", "yt": "y te"}
    assert result.dictionary_words == {"hom", "nay"}
    assert list(result.approved_details) == ["ko"]


def test_live_normalization_data_merges_db_phrase_overrides(tmp_path):
    PendingAbbreviationService.invalidate_live_normalization_cache()
    settings = Settings(data_dir=tmp_path)
    service = PendingAbbreviationService(settings)

    class FakeJsonStore:
        def load_abbreviations(self):
            return {}

        def load_dictionary_words(self):
            return {"hom", "nay"}

        def load_phrase_overrides(self):
            return {
                "do an co so": {
                    "expanded": "do an co so json",
                    "source": "override",
                    "confidence": 0.8,
                }
            }

        def load_mined_phrases(self):
            return {}

    class FakeRepository:
        def list_approved_abbreviations(self):
            return []

        def get_dictionary_words(self):
            return {"hom", "nay"}

    class FakePhraseOverrideRepository:
        def is_ready(self):
            return True

        def as_dict(self, domain=None):
            assert domain == "general"
            return {
                "dk hp": "dang ky hoc phan",
                "do an co so": "do an co so db",
            }

    service.json_store = FakeJsonStore()
    service.repository = FakeRepository()
    service.phrase_override_repository = FakePhraseOverrideRepository()
    service.db_is_ready = lambda: True  # type: ignore[method-assign]

    result = service.get_live_normalization_data(domain="general")

    assert result.phrase_overrides["dk hp"] == {
        "expanded": "dang ky hoc phan",
        "source": "db_override",
        "confidence": 1.0,
    }
    assert result.phrase_overrides["do an co so"] == {
        "expanded": "do an co so db",
        "source": "db_override",
        "confidence": 1.0,
    }


def test_live_normalization_data_does_not_apply_user_overrides(tmp_path):
    PendingAbbreviationService.invalidate_live_normalization_cache()
    settings = Settings(data_dir=tmp_path)
    service = PendingAbbreviationService(settings)

    class FakeJsonStore:
        def load_abbreviation_details(self):
            return {}

        def load_dictionary_words(self):
            return {"fallback"}

        def load_phrase_overrides(self):
            return {}

        def load_mined_phrases(self):
            return {}

    class FakeRepository:
        def list_approved_abbreviations(self):
            return [
                {
                    "id": "abbr-dk",
                    "abbr": "dk",
                    "expanded": "dang ky",
                    "alternative_expansions": ["dung khong"],
                    "domain": "general",
                    "source": "sql_server",
                }
            ]

        def get_dictionary_words(self):
            return {"hom", "nay"}

        def list_user_abbreviation_overrides(self, user_id, domain="general"):
            assert user_id == "user-1"
            assert domain == "general"
            return [
                {
                    "id": "override-dk",
                    "abbr": "dk",
                    "expanded": "dieu kien",
                    "alternative_expansions": ["du kien"],
                    "domain": domain,
                    "source": "user_personal",
                    "pending_id": "pending-dk",
                    "approved_abbreviation_id": None,
                    "created_at": None,
                }
            ]

    service.json_store = FakeJsonStore()
    service.repository = FakeRepository()
    service.db_is_ready = lambda: True  # type: ignore[method-assign]

    global_result = service.get_live_normalization_data(domain="general")
    user_result = service.get_live_normalization_data(domain="general", user_id="user-1")

    assert global_result.abbreviations["dk"] == "dang ky"
    assert user_result.abbreviations["dk"] == "dang ky"
    assert user_result.approved_details["dk"]["expanded"] == "dang ky"
    assert user_result.approved_details["dk"]["alternative_expansions"] == ["dung khong"]


def test_add_user_abbreviation_meaning_applies_personal_override_and_pending_review(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = PendingAbbreviationService(settings)
    calls = []

    class FakeRepository:
        def get_approved_abbreviation_details(self, abbr, domain="general"):
            return None

        def submit_pending_abbreviation(self, **kwargs):
            calls.append(("submit", kwargs))
            return {
                "abbr": kwargs["abbr"],
                "status": "PENDING_CREATED",
                "pending_id": "pending-dk",
                "has_suggested": True,
            }

        def capture_pending_suggestion(self, **kwargs):
            calls.append(("capture", kwargs))
            return {
                "pending_id": kwargs["pending_id"],
                "status": "SUGGESTION_CAPTURED",
                "suggested_meanings": [kwargs["suggested"]],
            }

        def upsert_user_abbreviation_override(self, **kwargs):
            calls.append(("override", kwargs))
            return {
                "id": "override-dk",
                "abbr": kwargs["abbr"],
                "expanded": kwargs["meaning"],
                "alternative_expansions": [],
                "domain": kwargs["domain"],
            }

    service.repository = FakeRepository()
    service.db_is_ready = lambda: True  # type: ignore[method-assign]

    result = service.add_user_abbreviation_meaning(
        abbr=" DK ",
        meaning=" dieu kien ",
        user_id="user-1",
        username="demo_user",
    )

    assert result["status"] == "USER_MEANING_APPLIED"
    assert result["review_required"] is True
    assert result["pending_id"] == "pending-dk"
    assert calls[0] == (
        "submit",
        {
            "abbr": "dk",
            "suggested": "dieu kien",
            "submitted_by": "demo_user",
            "source": "user_personal",
            "domain": "general",
        },
    )
    assert calls[1][0] == "capture"
    assert calls[1][1]["suggested"] == "dieu kien"
    assert calls[2][0] == "override"
    assert calls[2][1]["user_id"] == "user-1"


def test_add_user_abbreviation_meaning_reports_missing_override_schema(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = PendingAbbreviationService(settings)

    class FakeRepository:
        def get_approved_abbreviation_details(self, abbr, domain="general"):
            return None

        def submit_pending_abbreviation(self, **kwargs):
            return {
                "abbr": kwargs["abbr"],
                "status": "PENDING_CREATED",
                "pending_id": "pending-dk",
                "has_suggested": True,
            }

        def capture_pending_suggestion(self, **kwargs):
            return {
                "pending_id": kwargs["pending_id"],
                "status": "SUGGESTION_CAPTURED",
                "suggested_meanings": [kwargs["suggested"]],
            }

        def upsert_user_abbreviation_override(self, **kwargs):
            return {
                "abbr": kwargs["abbr"],
                "expanded": kwargs["meaning"],
                "status": "DB_SCHEMA_MISSING",
            }

    service.repository = FakeRepository()
    service.db_is_ready = lambda: True  # type: ignore[method-assign]

    result = service.add_user_abbreviation_meaning(
        abbr="dk",
        meaning="dieu kien",
        user_id="user-1",
        username="demo_user",
    )

    assert result["status"] == "DB_SCHEMA_MISSING"
    assert result["pending_id"] == "pending-dk"
    assert result["user_override"]["status"] == "DB_SCHEMA_MISSING"


def test_add_abbreviation_meaning_auto_approves_for_admin_flow(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = PendingAbbreviationService(settings)

    calls = []

    class FakeRepository:
        def submit_pending_abbreviation(self, **kwargs):
            calls.append(("submit", kwargs))
            return {
                "abbr": kwargs["abbr"],
                "status": "PENDING_CREATED",
                "pending_id": "pending-dk",
                "has_suggested": False,
            }

        def capture_pending_suggestion(self, **kwargs):
            calls.append(("capture", kwargs))
            return {"pending_id": kwargs["pending_id"], "status": "SUGGESTION_CAPTURED"}

        def approve_pending_abbreviation(self, **kwargs):
            calls.append(("approve", kwargs))
            return {
                "pending_id": kwargs["pending_id"],
                "abbreviation_id": "abbr-1",
                "status": "APPROVED",
            }

    service.repository = FakeRepository()
    service.db_is_ready = lambda: True  # type: ignore[method-assign]
    service.sync_approved_abbreviations_to_json = lambda: "ok"  # type: ignore[method-assign]
    service.get_approved_abbreviation_details = lambda abbr, domain="general": {  # type: ignore[method-assign]
        "abbr": abbr,
        "expanded": "điều kiện",
        "alternative_expansions": [],
        "domain": domain,
    }

    result = service.add_abbreviation_meaning(
        abbr="ĐK",
        meaning="điều khoản",
        reviewer="cli_admin",
        approve_immediately=True,
    )

    assert result["status"] == "APPROVED"
    assert calls[0][0] == "submit"
    assert calls[0][1]["abbr"] == "đk"
    assert calls[1][0] == "capture"
    assert calls[1][1]["suggested"] == "điều khoản"
    assert calls[2][0] == "approve"
    assert calls[2][1]["expanded"] == "điều khoản"


def test_add_abbreviation_meaning_skips_duplicate_approved_meaning(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = PendingAbbreviationService(settings)

    class FakeRepository:
        def submit_pending_abbreviation(self, **kwargs):
            raise AssertionError("Should not submit when meaning is already approved")

    service.repository = FakeRepository()
    service.db_is_ready = lambda: True  # type: ignore[method-assign]
    service.get_approved_abbreviation_details = lambda abbr, domain="general": {  # type: ignore[method-assign]
        "abbr": abbr,
        "expanded": "điều kiện",
        "alternative_expansions": ["điều khoản"],
        "domain": domain,
    }

    result = service.add_abbreviation_meaning(
        abbr="đk",
        meaning="điều khoản",
        reviewer="cli_admin",
        approve_immediately=True,
    )

    assert result["status"] == "MEANING_ALREADY_APPROVED"


def test_repeated_pending_submissions_are_replayed_from_cache():
    """Live normalize fires per keystroke; the same token must not re-hit the DB.

    Each submission wrote an UPDATE plus an audit-log row in its own
    transaction, so a single unknown word produced several writes per second.
    The replayed payload must stay complete — PendingNotice builds its form from
    ``pending_id``/``has_suggested``.
    """

    class _CountingRepository:
        def __init__(self):
            self.calls = 0

        def submit_pending_abbreviation(self, **kwargs):
            self.calls += 1
            return {
                "abbr": kwargs["abbr"],
                "status": "PENDING_CREATED",
                "pending_id": "pending-1",
                "has_suggested": False,
            }

    PendingAbbreviationService.invalidate_live_normalization_cache()
    settings = Settings(data_dir=Path(tempfile.mkdtemp()))
    service = PendingAbbreviationService(settings)
    repository = _CountingRepository()
    service.repository = repository

    first = service.submit_pending_abbreviation("zzz", submitted_by="demo")
    second = service.submit_pending_abbreviation("zzz", submitted_by="demo")

    assert repository.calls == 1
    assert first == second
    assert second["pending_id"] == "pending-1"
    assert second["has_suggested"] is False

    # A different token is not served from the first entry.
    service.submit_pending_abbreviation("yyy", submitted_by="demo")
    assert repository.calls == 2

    PendingAbbreviationService.invalidate_live_normalization_cache()
