from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.data_manager.ai_meaning_repo import AIMeaningRepository, metadata, evidence
from app.api.ai_meaning_routes import router, repository
from app.api.dependencies import get_current_user
from app.normalizer.ai_meanings import RequestMeanings
from app.normalizer.live_normalizer import (
    LiveNormalizerService,
    LiveNormalizationResult,
    LiveAmbiguity,
    LiveVariant,
)
from app.ai.semantic_verifier import VerificationResult


@pytest.fixture
def repo(tmp_path):
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"dbo": None}},
    )
    metadata.create_all(engine)
    settings = Settings(data_dir=tmp_path, app_env="development")
    yield AIMeaningRepository(settings, sessionmaker(engine))
    engine.dispose()


def record(repo, n=0, **overrides):
    values = dict(
        abbr="xyz",
        meaning="đăng ký",
        domain="education",
        context=f"xyz học phần {['hôm nay', 'ngày mai', 'tuần sau', 'kỳ tới'][n % 4]}",
        request_id=f"r{n}",
        user_id=f"u{n}",
        session_id=f"s{n}",
        confidence=0.85,
        provider="fake",
        model="fake",
    )
    return repo.record(**(values | overrides))


def promote(repo):
    for n in range(3):
        row = record(repo, n)
    assert row["status"] == "conditional_shared"
    return row


def test_independence_cache_retry_and_copy(repo):
    row = record(repo)
    for flag in ("from_cache", "retry", "reused"):
        assert record(repo, 1, **{flag: True}) is None
    record(repo, 1, request_id="r0")
    record(repo, 2, context="XYZ  học phần hôm nay!!!")
    assert repo.detail(row["id"])["candidate"]["evidence_count"] == 1
    assert len(repo.list()) == 1
    assert repo.reusable("xyz", "education", "xyz học phần hôm nay") is None


def test_short_context_is_captured_but_never_promoted(repo):
    for n, context in enumerate(["xyz", "xyz nhé", "xyz ạ"]):
        row = record(repo, n, context=context)
    assert row["evidence_count"] == 3
    assert row["status"] == "candidate"
    assert repo.reusable("xyz", "education", "xyz ạ") is None
    assert record(repo, context="https://example.com/xyz") is None


def test_dev_requires_three_sessions_and_prod_two_users(repo):
    for n in range(3):
        row = record(repo, n, session_id="one")
    assert row["status"] == "candidate"
    repo.settings = replace(repo.settings, app_env="production")
    row = record(repo, 3, session_id="one")
    assert row["status"] == "conditional_shared"


def test_production_one_user_cannot_promote(repo):
    repo.settings = replace(repo.settings, app_env="production")
    for n in range(3):
        row = record(repo, n, user_id="one")
    assert row["status"] == "candidate"
    assert record(repo, 3, user_id="two")["status"] == "conditional_shared"


def test_scope_conflict_revoke_and_tombstone(repo):
    row = promote(repo)
    assert repo.reusable("xyz", "education", "xyz học phần kỳ tới")["id"] == row["id"]
    assert repo.reusable("xyz", "other", "xyz học phần kỳ tới") is None
    assert repo.reusable("xyz", "education", "xyz địa chỉ nhà") is None
    other = record(repo, 3, meaning="xác nhận")
    assert other["status"] == "needs_review"
    assert repo.detail(row["id"])["candidate"]["status"] == "needs_review"
    assert repo.reusable("xyz", "education", "xyz học phần kỳ tới") is None
    with pytest.raises(ValueError, match="competing"):
        repo.moderate([row["id"]], "confirm", "admin", "checked")
    before = repo.revision()
    repo.moderate([other["id"]], "revoke", "admin", "wrong")
    repo.moderate([row["id"]], "confirm", "admin", "checked")
    assert repo.revision() > before
    assert record(repo, 3, meaning="xác nhận")["status"] == "revoked"
    assert repo.detail(other["id"])["audit"][0]["reason"] == "wrong"
    repo.moderate([row["id"]], "revoke", "admin", "retracted")
    assert repo.reusable("xyz", "education", "xyz học phần kỳ tới") is None


def test_private_evidence_and_bulk_atomicity(repo):
    row = record(
        repo, context="xyz học phần email jane@example.com mã ABC123 tên Nguyễn Văn An 0912345678"
    )
    with repo.factory() as session:
        item = dict(session.execute(select(evidence)).mappings().one())
    persisted = str(item)
    for private in ("jane", "example", "ABC123", "Nguyễn", "0912345678"):
        assert private not in persisted
    assert len(item["user_fingerprint"]) == 64
    assert item["user_fingerprint"] != item["session_fingerprint"]
    with pytest.raises(ValueError):
        repo.moderate([row["id"], str(uuid4())], "revoke", "admin", "bulk")
    assert repo.detail(row["id"])["candidate"]["status"] == "candidate"
    detail = repo.detail(row["id"])
    assert set(detail["evidence"][0]) == {"context_snippet", "created_at"}


def test_admin_api_authorization_and_actions(repo):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[repository] = lambda: repo
    client = TestClient(app)
    assert client.get("/api/admin/ai-meanings").status_code == 401
    app.dependency_overrides[get_current_user] = lambda: {"id": "u", "roles": ["user"]}
    assert client.get("/api/admin/ai-meanings").status_code == 403
    assert (
        client.post(
            "/api/admin/ai-meanings/moderate",
            json={"ids": [str(uuid4())], "action": "revoke", "reason": "x"},
        ).status_code
        == 403
    )
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin", "roles": ["admin"]}
    row = record(repo)
    assert client.get("/api/admin/ai-meanings?status=candidate").json()[0]["id"] == row["id"]
    assert client.get(f"/api/admin/ai-meanings/{row['id']}").status_code == 200
    response = client.post(
        "/api/admin/ai-meanings/moderate",
        json={"ids": [row["id"]], "action": "revoke", "reason": "wrong"},
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "revoked"


def baseline():
    return LiveNormalizationResult(
        "xyz học phần hôm nay",
        [LiveVariant("main", "xyz học phần hôm nay", is_primary=True)],
        [LiveAmbiguity("x", "xyz", 0, [], "xyz")],
        [],
        [],
        [],
        0,
        semantic_status="not_checked",
    )


@pytest.mark.asyncio
async def test_live_fake_ai_capture_cache_and_reuse(repo):
    class Verifier:
        def is_available(self):
            return True

        async def verify(self, **kwargs):
            return VerificationResult(
                "đăng ký học phần hôm nay", [("xyz", "đăng ký")], 0.85, False, 1, verified_chunks=1
            )

    meanings = RequestMeanings(
        repo, request_id="live", user_id="one", session_id="session", domain="education"
    )
    service = LiveNormalizerService(
        repo.settings, SimpleNamespace(), semantic_verifier=Verifier(), request_meanings=meanings
    )
    result = await service.apply_semantic_verification(baseline(), "xyz học phần hôm nay")
    assert result.primary_output == "Đăng ký học phần hôm nay"
    assert repo.list()[0]["evidence_count"] == 1
    # Same request cannot strengthen evidence even if inference is repeated.
    await service.apply_semantic_verification(baseline(), "xyz học phần hôm nay")
    assert repo.list()[0]["evidence_count"] == 1
    record(repo, 1)
    record(repo, 2)
    row = repo.list()[0]
    assert row["status"] == "conditional_shared"
    reused = await service.apply_semantic_verification(baseline(), "xyz học phần hôm nay")
    assert reused.semantic_status_reason == "conditional_shared_meaning"
    assert reused.expanded_abbreviations[0]["candidateId"] == row["id"]
    assert repo.list()[0]["evidence_count"] == 3
    repo.moderate([row["id"]], "revoke", "admin", "wrong")
    assert not await service.dictionary_is_current()
    next_meanings = RequestMeanings(
        repo, request_id="next", user_id="one", session_id="session", domain="education"
    )
    next_result = baseline()
    next_meanings.reuse("xyz học phần hôm nay", next_result)
    assert next_result.primary_output.startswith("xyz")


@pytest.mark.asyncio
async def test_revocation_while_ai_is_running_returns_original_baseline(repo):
    row = promote(repo)

    class RevokingVerifier:
        def is_available(self):
            return True

        async def verify(self, **kwargs):
            repo.moderate([row["id"]], "revoke", "admin", "while running")
            return VerificationResult(
                "đăng ký học phần hôm nay", [], 0.9, False, 1, verified_chunks=1
            )

    meanings = RequestMeanings(
        repo, request_id="running", user_id="one", session_id="session", domain="education"
    )
    service = LiveNormalizerService(
        repo.settings,
        SimpleNamespace(),
        semantic_verifier=RevokingVerifier(),
        request_meanings=meanings,
    )
    value = baseline()
    value.ambiguities.append(LiveAmbiguity("y", "other", 1, [], "other"))
    result = await service.apply_semantic_verification(value, "xyz học phần hôm nay")
    assert result.primary_output == "xyz học phần hôm nay"
    assert result.semantic_status_reason == "dictionary_changed"
    assert result.expanded_abbreviations == []


def test_evidence_failure_is_visible_and_cache_corrections_do_not_write(repo):
    meanings = RequestMeanings(
        repo, request_id="x", user_id="one", session_id="session", domain="education"
    )
    result = baseline()
    cached = VerificationResult(
        "đăng ký học phần hôm nay", [("xyz", "đăng ký")], 0.9, True, 1, verified_chunks=1
    )
    meanings.capture("xyz học phần hôm nay", {"xyz": []}, cached, result)
    assert repo.list() == []

    def fail(**kwargs):
        raise RuntimeError("storage unavailable")

    repo.record = fail
    meanings.capture("xyz học phần hôm nay", {"xyz": []}, replace(cached, from_cache=False), result)
    assert "ai_meaning_evidence_write_failed" in result.warnings


def test_partially_cached_verification_only_records_fresh_corrections(repo):
    meanings = RequestMeanings(
        repo, request_id="mixed", user_id="one", session_id="session", domain="education"
    )
    verification = VerificationResult(
        "đăng ký học phần hôm nay",
        [("xyz", "đăng ký")],
        0.9,
        False,
        1,
        verified_chunks=2,
        evidence_corrections=[],
    )
    meanings.capture("xyz học phần hôm nay", {"xyz": []}, verification, baseline())
    assert repo.list() == []


def test_workspace_api_creates_reuses_and_revokes_with_fake_ai(repo, monkeypatch):
    from app.api import routes
    from app.api.dependencies import get_app_settings
    from app.api.server import create_app
    from app.data_manager.pending_service import LiveNormalizationData

    class Dataset:
        def get_live_normalization_data(self, **kwargs):
            return LiveNormalizationData(
                {}, frozenset("học phần hôm nay ngày mai tuần sau kỳ tới".split()), {}
            )

        def submit_pending_abbreviation(self, **kwargs):
            return {"abbr": kwargs["abbr"], "status": "SKIPPED"}

    class Verifier:
        calls = 0

        def is_available(self):
            return True

        async def verify(self, **kwargs):
            self.calls += 1
            output = kwargs["text"].replace("Xyz", "Đăng ký").replace("xyz", "đăng ký")
            return VerificationResult(
                output, [("xyz", "đăng ký")], 0.9, False, 1, verified_chunks=1
            )

    verifier = Verifier()
    monkeypatch.setattr(
        "app.data_manager.ai_meaning_repo.AIMeaningRepository", lambda settings: repo
    )
    monkeypatch.setattr(routes, "get_semantic_verifier", lambda settings: verifier)
    monkeypatch.setattr(routes, "get_shared_word_map", lambda path: {})
    monkeypatch.setattr(routes, "get_shared_bigram_freq", lambda path: {})
    monkeypatch.setattr(routes, "get_shared_context_phrase_overrides", lambda path: {})
    monkeypatch.setattr(
        routes, "UsageStatsRepository", lambda settings: SimpleNamespace(is_ready=lambda: False)
    )
    app = create_app()
    app.dependency_overrides[get_app_settings] = lambda: repo.settings
    app.dependency_overrides[routes._get_pending_service] = Dataset
    actor = {"id": "u", "username": "test", "roles": ["admin"]}
    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[repository] = lambda: repo
    client = TestClient(app)
    for n, suffix in enumerate(["hôm nay", "ngày mai", "tuần sau"]):
        actor["id"] = f"u{n}"
        response = client.post(
            "/api/normalize/live",
            headers={"Authorization": f"Bearer session{n}"},
            json={"text": f"xyz học phần {suffix}", "domain": "education", "allowAI": True},
        )
        assert response.status_code == 200, response.text
    assert verifier.calls == 3
    row = repo.list()[0]
    assert row["status"] == "conditional_shared"
    body = {"text": "xyz học phần kỳ tới", "domain": "education", "allowAI": True}
    reused = client.post(
        "/api/normalize/live", json=body, headers={"Authorization": "Bearer session4"}
    ).json()
    assert verifier.calls == 3
    assert reused["semanticStatusReason"] == "conditional_shared_meaning"
    assert reused["changes"][0]["candidateId"] == row["id"]
    dataset = client.post("/api/normalize/live", json=body | {"allowAI": False}).json()
    assert "xyz" in dataset["primaryOutput"].lower()
    assert repo.list()[0]["evidence_count"] == 3
    revoked = client.post(
        "/api/admin/ai-meanings/moderate",
        json={"ids": [row["id"]], "action": "revoke", "reason": "wrong"},
    )
    assert revoked.status_code == 200
    after = client.post(
        "/api/normalize/live", json=body, headers={"Authorization": "Bearer session4"}
    ).json()
    assert verifier.calls == 4  # must infer afresh; never reuse the revoked row
    assert not any(s["source"] == "ai_conditional" for s in after["expandedAbbreviations"])
    assert repo.list()[0]["status"] == "revoked"
