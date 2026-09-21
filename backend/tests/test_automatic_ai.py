import json

import pytest

from app.ai.client import AIRequest, AIResponse
from app.ai.semantic_verifier import SemanticVerifier
from app.api.routes import _should_apply_semantic_verification
from app.config import Settings
from types import SimpleNamespace


def test_short_ambiguous_text_and_single_diacritic_change_trigger_ai():
    for result in (
        SimpleNamespace(ambiguities=["dk"]),
        SimpleNamespace(diacritic_applied=True, diacritic_changes=[("toi", "tôi")]),
    ):
        for method in ("typing", "paste"):
            assert _should_apply_semantic_verification(method, "dk", result, Settings())


class RewritingClient:
    def __init__(self, output, confidence=1):
        self.output = output
        self.confidence = confidence
        self.requests: list[AIRequest] = []

    def is_available(self):
        return True

    async def complete(self, request):
        self.requests.append(request)
        return AIResponse(
            json.dumps(
                {"verified_text": self.output, "confidence": self.confidence, "corrections": []}
            ),
            0,
            0,
            "fake",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("output", ["Dk https://evil.test", "Dk https://safe.test\nnew", ""])
async def test_rejects_changes_to_literals_or_layout(output):
    source = "dk https://safe.test"
    verifier = SemanticVerifier(RewritingClient(output))
    result = await verifier.verify(source, abbreviation_options={"dk": ["đăng ký"]})
    assert result.verified_text == source
    assert result.status == "uncertain"


@pytest.mark.asyncio
async def test_nonfinite_confidence_cannot_accept_rewrite():
    verifier = SemanticVerifier(RewritingClient("wrong", float("nan")))
    result = await verifier.verify("dk", abbreviation_options={"dk": ["đăng ký"]})
    assert result.verified_text == "dk"
    assert result.status == "uncertain"
