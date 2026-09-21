"""Local-only E2E fixture: real routes/auth, in-memory repositories, fake AI."""

import asyncio
import json
import re
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_api import ApiTests
from app.ai.admission import BudgetedClient
from app.ai.client import AIResponse
from app.ai.semantic_verifier import SemanticVerifier
from app.api.dependencies import get_current_user
import app.api.routes as routes


class FakeAI:
    model = "deterministic-e2e"

    def is_available(self):
        return True

    async def complete(self, request):
        await asyncio.sleep(1.2)
        source = request.prompt.split('Output hiện tại cần kiểm tra:\n"')[1].split('"\n')[0]
        output = re.sub(r"\b(?:dk|đk)\b", "đăng ký", source, flags=re.IGNORECASE)
        return AIResponse(
            json.dumps({"verified_text": output, "confidence": 0.95, "corrections": []}),
            10,
            1200,
            self.model,
        )


def create_fixture():
    fixture = ApiTests()
    fixture.setUp()
    directory = tempfile.TemporaryDirectory(prefix="normalizer-e2e-")
    fixture.settings = replace(
        fixture.settings,
        data_dir=Path(directory.name),
        ai_disable_network=True,
        diacritic_auto_detect=False,
        ai_budget_path=str(Path(directory.name) / "budget.sqlite3"),
        ai_requests_per_window=100,
        ai_user_requests_per_window=100,
        auth_secret="isolated-e2e-auth-secret-32-characters",
        semantic_verify_max_tokens=8,
    )
    fixture.auth_service.settings = fixture.settings
    original_login = fixture.auth_service.login

    def login(identifier, password):
        result = original_login(identifier, password)
        if result.get("access_token"):
            fixture.session_repository.valid_tokens.add(result["access_token"])
        return result

    fixture.auth_service.login = login
    del fixture.app.dependency_overrides[get_current_user]
    verifier = SemanticVerifier(
        BudgetedClient(FakeAI(), fixture.settings, "fake-only"),
        max_tokens=8,
        max_chunks=32,
        max_concurrency=1,
    )
    routes.get_semantic_verifier = lambda settings: verifier
    routes.UsageStatsRepository = lambda settings: SimpleNamespace(
        record_usage_bulk=lambda *a, **k: None
    )

    @fixture.app.get("/__test/session")
    def session():
        return {
            "token": fixture._issue_token("user-1"),
            "user": fixture.user_repository.users["user-1"],
        }

    fixture.app.state.fixture_directory = directory
    return fixture.app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_fixture(), host="127.0.0.1", port=8016)
