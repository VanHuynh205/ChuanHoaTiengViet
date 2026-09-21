from unittest.mock import Mock
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import Settings
from app.data_manager.pending_service import PendingAbbreviationService


def test_export_failure_preserves_committed_save_and_invalidates(tmp_path):
    service = PendingAbbreviationService(Settings(data_dir=tmp_path))
    service.db_is_ready = lambda: True
    record = {"id": "1", "abbr": "dk", "expanded": "đăng ký", "domain": "general"}
    service.repository = Mock()
    service.repository.get_approved_abbreviation_details.return_value = record
    service.repository.list_approved_abbreviations.return_value = [record]
    service.json_store.export_approved_abbreviations = Mock(side_effect=OSError("disk full"))
    before = service.live_normalization_cache_generation()
    result = service.save_approved_abbreviation("dk", "đăng ký", "admin")
    assert result["expanded"] == "đăng ký"
    assert result["dictionary_sync"]["status"] == "export_failed"
    assert result["dictionary_sync"]["database_committed"] is True
    assert service.live_normalization_cache_generation() > before
    assert service.dictionary_sync_status()["status"] == "export_failed"


def test_readback_failure_is_reported_as_committed_by_api(tmp_path):
    from dataclasses import replace
    from test_api import ApiTests
    fixture = ApiTests()
    fixture.setUp()
    fixture.settings = replace(fixture.settings, data_dir=tmp_path)
    service = PendingAbbreviationService(fixture.settings)
    service.db_is_ready = lambda: True
    service.repository = Mock()
    service.repository.list_approved_abbreviations.return_value = []
    service.repository.get_approved_abbreviation_details.side_effect = RuntimeError("read failed")
    fixture.pending_service = service
    try:
        response = fixture.client.put("/api/abbreviations/dk", json={"expanded": "đăng ký"})
        assert response.status_code == 503
        assert response.json()["database_committed"] is True
        assert "Đã lưu" in response.json()["detail"]
        service.repository.bulk_upsert_abbreviations.assert_called_once()
    finally:
        fixture.tearDown()


@pytest.mark.parametrize("fail_export", [False, True])
def test_two_api_workers_refresh_cached_dataset_after_admin_save(tmp_path, fail_export):
    worker = Path(__file__).with_name("dictionary_worker.py")
    processes = [subprocess.Popen([sys.executable, str(worker), str(tmp_path)],
                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                 text=True, encoding="utf-8") for _ in range(2)]

    def call(process, **command):
        process.stdin.write(json.dumps(command) + "\n")
        process.stdin.flush()
        line = process.stdout.readline()
        assert line, "worker exited before producing an API response"
        value = json.loads(line)
        assert value["status"] == 200, value
        return value["body"]

    try:
        for process in processes:
            for _ in range(2):
                assert "đăng ký" in call(process, op="read")["primaryOutput"]
        saved = call(processes[0], op="save", meaning="điều kiện", fail_export=fail_export)
        assert saved["dictionary_sync"]["database_committed"]
        assert saved["dictionary_sync"]["status"] == ("export_failed" if fail_export else "synced")
        for process in processes:
            output = call(process, op="read")["primaryOutput"]
            assert "điều kiện" in output
            assert "đăng ký" not in output
            assert call(process, op="status")["revision"] == saved["dictionary_sync"]["revision"]
    finally:
        for process in processes:
            process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def test_sync_endpoints_enforce_real_jwt_admin_role(tmp_path):
    from dataclasses import replace
    from test_api import ApiTests
    from app.api.dependencies import get_current_user

    fixture = ApiTests()
    fixture.setUp()
    fixture.settings = replace(fixture.settings, data_dir=tmp_path)
    del fixture.app.dependency_overrides[get_current_user]
    user = {"Authorization": "Bearer " + fixture._issue_token("user-1")}
    admin = {"Authorization": "Bearer " + fixture._issue_token("admin-1")}
    try:
        assert fixture.client.get("/api/dictionary/revision").status_code == 401
        assert fixture.client.get("/api/dictionary/revision", headers=user).status_code == 200
        assert fixture.client.get("/api/admin/dictionary/sync-status", headers=user).status_code == 403
        assert fixture.client.post("/api/admin/dictionary/retry-export", headers=user).status_code == 403
        assert fixture.client.get("/api/admin/dictionary/sync-status", headers=admin).status_code == 200
    finally:
        fixture.tearDown()


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_late_ai_does_not_apply_after_dictionary_revision_changes(tmp_path, stream):
    from test_live_normalizer import FakePendingService
    from test_semantic_verifier import _StubClient, _StubResponse
    from app.ai.semantic_verifier import SemanticVerifier
    from app.normalizer.live_normalizer import LiveNormalizerService
    from app.api.live_stream import stream_verification

    revision = [0]
    pending = FakePendingService()
    pending.dictionary_revision = lambda: revision[0]
    client = _StubClient()

    async def late_reply(request):
        revision[0] += 1
        return _StubResponse(json.dumps({"verified_text": "Kết quả cũ của AI", "confidence": 0.95}))

    client.complete.side_effect = late_reply
    service = LiveNormalizerService(Settings(data_dir=tmp_path), pending,
        semantic_verifier=SemanticVerifier(client, max_tokens=4))
    source = "hôm nay đi đk thẻ ngân hàng pk"
    baseline = service.normalize_live(source)
    original_output = baseline.primary_output
    if stream:
        response = stream_verification(service, baseline, source, {}, "user")
        snapshots = [json.loads(value) async for value in response.body_iterator]
        assert all(item["result"]["primaryOutput"] == original_output for item in snapshots)
        assert snapshots[-1]["result"]["semanticStatusReason"] == "dictionary_changed"
    else:
        result = await service.apply_semantic_verification(baseline, source)
        assert result.primary_output == original_output
        assert result.semantic_status_reason == "dictionary_changed"
