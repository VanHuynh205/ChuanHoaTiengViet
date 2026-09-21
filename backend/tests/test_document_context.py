import json

import pytest

from app.ai.client import AIResponse
from app.ai.errors import AIRateLimitError
from app.ai.semantic_verifier import SemanticVerifier


class ContextClient:
    def __init__(self, limit=99):
        self.calls = []
        self.limit = limit

    def is_available(self):
        return True

    async def complete(self, request):
        self.calls.append(request)
        if len(self.calls) > self.limit:
            raise AIRateLimitError("fake quota")
        text = request.prompt.split('Output hiện tại cần kiểm tra:\n"')[1].split('"\n')[0]
        if "đăng ký học phần" in request.prompt:
            text = text.replace("dkhp", "đăng ký học phần")
        return AIResponse(
            json.dumps({"verified_text": text, "confidence": 0.95, "corrections": []}), 0, 0, "fake"
        )


@pytest.mark.asyncio
async def test_previous_definition_reaches_next_chunk_and_progress_is_emitted():
    text = "đăng ký học phần (dkhp).\n\nmai dkhp nhé."
    client = ContextClient()
    progress = []

    async def receive(result):
        progress.append(result)

    result = await SemanticVerifier(client, max_tokens=5).verify(
        text, abbreviation_options={"dkhp": ["dkhp"]}, on_progress=receive
    )
    assert "mai đăng ký học phần" in result.verified_text.lower()
    assert "\n\n" in result.verified_text
    assert progress
    assert "đăng ký học phần" in client.calls[-1].prompt


@pytest.mark.asyncio
async def test_five_thousand_words_survive_budget_exhaustion():
    text = "\n\n".join([" ".join(["dkhp"] * 200)] * 25)
    progress = []

    async def receive(result):
        progress.append(result)

    result = await SemanticVerifier(ContextClient(limit=1), max_tokens=200, max_chunks=25).verify(
        text, abbreviation_options={"dkhp": ["dkhp"]}, on_progress=receive
    )
    assert len(result.verified_text.split()) == 5000
    assert result.verified_text.count("\n\n") == 24
    assert result.total_chunks == 25
    assert result.verified_chunks == 1
    assert result.status == "partial"
    assert len(progress) == 25
