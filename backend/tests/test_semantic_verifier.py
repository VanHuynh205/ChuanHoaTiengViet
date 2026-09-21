"""Tests for SemanticVerifier."""

from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest

from app.ai.errors import AITimeoutError
from app.ai.semantic_verifier import (
    SemanticVerifier,
    _build_ambiguous_positions,
    _parse_verify_response,
)

# --- Stub AI client ---


@dataclass
class _StubResponse:
    text: str


class _StubClient:
    """Minimal AI client stub for testing."""

    def __init__(self, response_text: str = "", available: bool = True):
        self._response_text = response_text
        self._available = available
        self.complete = AsyncMock(return_value=_StubResponse(text=response_text))

    def is_available(self) -> bool:
        return self._available


class _ConcurrencyProbeClient:
    def __init__(self):
        self.active = 0
        self.max_active = 0
        self.complete = AsyncMock(side_effect=self._complete)

    def is_available(self) -> bool:
        return True

    async def _complete(self, _request):
        import asyncio

        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return _StubResponse(
            text=json.dumps(
                {
                    "verified_text": "ok",
                    "corrections": [],
                    "confidence": 0.9,
                }
            )
        )


# --- Unit tests ---


class TestParseVerifyResponse:
    def test_plain_json(self):
        raw = '{"verified_text": "nghe nói", "corrections": [], "confidence": 0.95}'
        result = _parse_verify_response(raw)
        assert result["verified_text"] == "nghe nói"
        assert result["confidence"] == 0.95

    def test_json_in_markdown_fence(self):
        raw = '```json\n{"verified_text": "test", "corrections": [], "confidence": 0.8}\n```'
        result = _parse_verify_response(raw)
        assert result["verified_text"] == "test"

    def test_json_with_corrections(self):
        raw = json.dumps(
            {
                "verified_text": "nghe nói",
                "corrections": [["nghệ", "nghe"], ["nội", "nói"]],
                "confidence": 0.92,
            }
        )
        result = _parse_verify_response(raw)
        assert len(result["corrections"]) == 2

    def test_json_allows_provider_control_characters_inside_text(self):
        # Some NVIDIA responses contain a literal newline/tab in the JSON
        # string even though the HTTP response itself is valid JSON.
        raw = '{"verified_text": "dong mot\ndong hai\tok", "corrections": [], "confidence": 0.8}'
        result = _parse_verify_response(raw)
        assert result["verified_text"] == "dong mot\ndong hai\tok"


class TestBuildAmbiguousPositions:
    def test_with_diacritic_candidates(self):
        result = _build_ambiguous_positions(
            "test",
            diacritic_candidates={"nghe": ["nghệ", "nghe"]},
        )
        assert "nghe" in result
        assert "nghệ" in result

    def test_with_abbreviation_options(self):
        result = _build_ambiguous_positions(
            "test",
            abbreviation_options={"dc": ["được", "địa chỉ"]},
        )
        assert "dc" in result
        assert "viết tắt" in result

    def test_empty_returns_placeholder(self):
        result = _build_ambiguous_positions("test")
        assert result == "(không có)"


# --- Async integration tests ---


@pytest.mark.asyncio
class TestSemanticVerifier:
    async def test_semantic_requests_disable_reasoning_for_latency(self):
        client = _StubClient(json.dumps({
            "verified_text": "tôi đi học",
            "corrections": [],
            "confidence": 0.95,
        }))
        verifier = SemanticVerifier(ai_client=client, confidence_threshold=0.7)

        result = await verifier.verify("toi di hoc", diacritic_candidates={"toi": ["tôi"]})

        assert result.status == "verified"
        request = client.complete.await_args.args[0]
        assert request.enable_thinking is False

    async def test_dictionary_revision_prevents_reusing_old_ai_result(self):
        client = _StubClient(json.dumps({"verified_text": "đăng ký học phần",
                                        "confidence": 0.9, "corrections": []}))
        verifier = SemanticVerifier(ai_client=client)
        args = {"text": "dk học phần", "abbreviation_options": {"dk": ["dk"]}}
        await verifier.verify(**args, cache_namespace="1")
        await verifier.verify(**args, cache_namespace="1")
        await verifier.verify(**args, cache_namespace="2")
        assert client.complete.call_count == 2

    async def test_inferred_teencode_cannot_remove_protected_url(self):
        client = _StubClient(json.dumps({"verified_text": "đăng ký học phần",
                                        "confidence": 0.55, "corrections": []}))
        verifier = SemanticVerifier(ai_client=client, confidence_threshold=0.7)
        source = "dk học phần https://example.com"
        result = await verifier.verify(text=source, abbreviation_options={"dk": ["dk"]})
        assert result.verified_text == source

    async def test_best_effort_teencode_rewrite_survives_low_confidence_and_cache(self):
        client = _StubClient(json.dumps({"verified_text": "đăng ký học phần",
                                        "corrections": [["dk", "đăng ký"]],
                                        "confidence": 0.55}))
        verifier = SemanticVerifier(ai_client=client, confidence_threshold=0.7)
        for _ in range(2):
            result = await verifier.verify(text="dk học phần", abbreviation_options={"dk": ["dk"]})
            assert result.verified_text == "Đăng ký học phần"
            assert result.status == "uncertain"
        assert client.complete.call_count == 1

    async def test_returns_corrections_above_threshold(self):
        response = json.dumps(
            {
                "verified_text": "nghe nói",
                "corrections": [["nghệ", "nghe"], ["nội", "nói"]],
                "confidence": 0.92,
            }
        )
        client = _StubClient(response_text=response)
        verifier = SemanticVerifier(ai_client=client, confidence_threshold=0.7)
        result = await verifier.verify(
            text="nghệ nội",
            diacritic_candidates={"nghe": ["nghệ", "nghe"]},
        )
        assert result.verified_text == "Nghe nói"
        assert len(result.corrections) == 2
        assert result.confidence == 0.92
        assert result.from_cache is False
        request = client.complete.call_args[0][0]
        assert request.json_mode is True
        assert request.temperature == 0.1

    async def test_below_threshold_keeps_original(self):
        response = json.dumps(
            {
                "verified_text": "nghe nói",
                "corrections": [["nghệ", "nghe"]],
                "confidence": 0.3,
            }
        )
        client = _StubClient(response_text=response)
        verifier = SemanticVerifier(ai_client=client, confidence_threshold=0.7)
        result = await verifier.verify(
            text="nghệ nội",
            diacritic_candidates={"nghe": ["nghệ", "nghe"]},
        )
        assert result.verified_text == "nghệ nội"
        assert result.corrections == []
        assert result.confidence == 0.3

    async def test_cache_hit(self):
        response = json.dumps(
            {
                "verified_text": "nghe nói",
                "corrections": [],
                "confidence": 0.95,
            }
        )
        client = _StubClient(response_text=response)
        verifier = SemanticVerifier(ai_client=client, confidence_threshold=0.7)

        # First call
        await verifier.verify(
            text="nghệ nội",
            diacritic_candidates={"nghe": ["nghệ", "nghe"]},
        )
        # Second call should be cached
        result = await verifier.verify(
            text="nghệ nội",
            diacritic_candidates={"nghe": ["nghệ", "nghe"]},
        )
        assert result.from_cache is True
        # AI should have been called only once
        assert client.complete.call_count == 1

    async def test_no_ambiguities_returns_immediately(self):
        client = _StubClient(response_text="{}")
        verifier = SemanticVerifier(ai_client=client, confidence_threshold=0.7)

        result = await verifier.verify(text="hello world")
        assert result.verified_text == "hello world"
        assert result.confidence == 1.0
        assert result.latency_ms == 0
        assert client.complete.call_count == 0

    async def test_unavailable_client_returns_original(self):
        client = _StubClient(response_text="{}", available=False)
        verifier = SemanticVerifier(ai_client=client, confidence_threshold=0.7)
        assert verifier.is_available() is False

    async def test_ai_error_falls_back_gracefully(self):
        client = _StubClient(response_text="not json at all {{{")
        verifier = SemanticVerifier(ai_client=client, confidence_threshold=0.7)

        result = await verifier.verify(
            text="test text",
            diacritic_candidates={"test": ["tést", "test"]},
        )
        # Should fall back to original text
        assert result.verified_text == "test text"
        assert result.confidence == 0.0

    async def test_ai_timeout_falls_back_without_traceback_log(self, caplog):
        client = _StubClient()
        client.complete.side_effect = AITimeoutError("NVIDIA request timed out")
        verifier = SemanticVerifier(ai_client=client, confidence_threshold=0.7)

        with caplog.at_level("WARNING", logger="app.ai.semantic_verifier"):
            result = await verifier.verify(
                text="test text",
                diacritic_candidates={"test": ["t\u00e9st", "test"]},
            )

        assert result.verified_text == "test text"
        assert result.confidence == 0.0
        assert "Semantic verification unavailable; keeping rule-based output" in caplog.text
        assert all(record.exc_info is None for record in caplog.records)

    async def test_long_text_verifies_candidate_chunk_without_truncating_full_output(self):
        long_text = " ".join([f"word{i}" for i in range(100)])
        response = json.dumps(
            {
                "verified_text": "truncated",
                "corrections": [],
                "confidence": 0.9,
            }
        )
        client = _StubClient(response_text=response)
        verifier = SemanticVerifier(ai_client=client, confidence_threshold=0.7, max_tokens=20)
        result = await verifier.verify(
            text=long_text,
            diacritic_candidates={"word99": ["wórd99", "word99"]},
        )
        assert result.verified_text.startswith("Word0 word1 word2")
        assert result.verified_text.endswith("Truncated")
        assert result.confidence == 0.9
        assert client.complete.call_count == 1
        prompt = client.complete.call_args[0][0].prompt
        assert "word80" in prompt
        assert "word99" in prompt
        assert "word0" not in prompt

    async def test_long_text_keeps_unverified_chunks_and_verifies_only_matching_chunk(self):
        long_text = "alpha beta gamma delta. " "need fix here now. " "tail words stay same."
        response = json.dumps(
            {
                "verified_text": "need fixed here now.",
                "corrections": [["fix", "fixed"]],
                "confidence": 0.92,
            }
        )
        client = _StubClient(response_text=response)
        verifier = SemanticVerifier(
            ai_client=client,
            confidence_threshold=0.7,
            max_tokens=4,
            max_chunks=5,
        )

        result = await verifier.verify(
            text=long_text,
            diacritic_candidates={"fix": ["fix", "fixed"]},
        )

        assert result.verified_text == (
            "Alpha beta gamma delta. Need fixed here now. Tail words stay same."
        )
        assert result.corrections == [("fix", "fixed")]
        assert result.confidence == 0.92
        assert result.total_chunks == 3
        assert result.verified_chunks == 1
        assert client.complete.call_count == 1
        prompt = client.complete.call_args[0][0].prompt
        assert "need fix here now" in prompt
        assert "alpha beta gamma delta" in prompt

    async def test_full_text_review_skips_clean_chunks_but_reports_full_coverage(self):
        client = _StubClient(response_text=json.dumps({
            "verified_text": "alpha beta gamma delta. need fixed here now. tail words stay same.",
            "corrections": [["fix", "fixed"]],
            "confidence": 0.92,
        }))
        verifier = SemanticVerifier(ai_client=client, confidence_threshold=0.7, max_tokens=4)
        result = await verifier.verify(
            text="alpha beta gamma delta. need fix here now. tail words stay same.",
            diacritic_candidates={"fix": ["fix", "fixed"]},
            review_all=True,
            source_text="alpha beta gamma delta. need fix here now. tail words stay same.",
        )
        assert result.verified_text.startswith("Alpha beta gamma delta. Need fixed")
        assert result.total_chunks == result.verified_chunks
        assert client.complete.call_count == 1

    async def test_long_text_respects_max_ai_chunks(self):
        long_text = "first fix one now. " "second issue two now. " "third clean chunk now."
        response = json.dumps(
            {
                "verified_text": "first fixed one now.",
                "corrections": [["fix", "fixed"]],
                "confidence": 0.9,
            }
        )
        client = _StubClient(response_text=response)
        verifier = SemanticVerifier(
            ai_client=client,
            confidence_threshold=0.7,
            max_tokens=4,
            max_chunks=1,
        )

        result = await verifier.verify(
            text=long_text,
            diacritic_candidates={
                "fix": ["fix", "fixed"],
                "issue": ["issue", "issued"],
            },
        )

        assert result.verified_text == (
            "First fixed one now. Second issue two now. Third clean chunk now."
        )
        assert result.verified_chunks == 1
        assert result.skipped_chunks == 1
        assert client.complete.call_count == 1

    async def test_long_text_verification_runs_chunk_calls_with_bounded_concurrency(self):
        client = _ConcurrencyProbeClient()
        verifier = SemanticVerifier(
            ai_client=client,
            confidence_threshold=0.7,
            max_tokens=3,
            max_chunks=3,
            max_concurrency=2,
        )

        result = await verifier.verify(
            text="first fix now. second fix now. third fix now.",
            diacritic_candidates={"fix": ["fix", "fixed"]},
        )

        assert result.verified_chunks == 3
        assert client.complete.call_count == 3
        assert client.max_active == 2

    async def test_abbreviation_options_prompt_allows_ai_to_choose_contextually(self):
        response = json.dumps(
            {
                "verified_text": "hôm nay đi đúng không thẻ ngân hàng",
                "corrections": [["đăng ký", "đúng không"]],
                "confidence": 0.91,
            }
        )
        client = _StubClient(response_text=response)
        verifier = SemanticVerifier(ai_client=client, confidence_threshold=0.7)

        result = await verifier.verify(
            text="hôm nay đi đăng ký thẻ ngân hàng",
            abbreviation_options={"đk": ["đăng ký", "đúng không"]},
        )

        assert result.verified_text == "Hôm nay đi đúng không thẻ ngân hàng"
        prompt = client.complete.call_args[0][0].prompt
        assert "đk" in prompt
        assert "đúng không" in prompt


@pytest.mark.asyncio
async def test_long_text_without_ai_calls_preserves_original_formatting():
    """A run where every chunk is filtered out must not rewrite the user's text.

    Joining chunks with a single space used to delete every blank line and then
    report the mangled result as an AI-verified correction.
    """

    class _NoCallClient:
        def is_available(self):
            return True

        async def complete(self, request):  # pragma: no cover - must never run
            raise AssertionError("AI must not be called when no chunk has candidates")

    text = "Doan mot voi kha nhieu tu o day.\n\nDoan hai cung dai khong kem canh gi."
    verifier = SemanticVerifier(ai_client=_NoCallClient(), max_tokens=5)

    result = await verifier.verify(text, diacritic_candidates={"khongcotrongtext": ["x"]})

    assert result.verified_text == text
    assert result.verified_chunks == 0
    assert result.corrections == []


@pytest.mark.asyncio
async def test_low_confidence_result_is_not_served_from_cache_as_a_correction():
    """The cache must store the value we return, not the raw model reply."""

    class _LowConfidenceClient:
        def __init__(self):
            self.calls = 0

        def is_available(self):
            return True

        async def complete(self, request):
            self.calls += 1
            from app.ai.client import AIResponse

            return AIResponse(
                text='{"verified_text": "AI DA GHI DE SAI", "corrections": [], "confidence": 0.1}',
                tokens_used=0,
                latency_ms=1,
                model="fake",
            )

    client = _LowConfidenceClient()
    verifier = SemanticVerifier(ai_client=client, confidence_threshold=0.7)

    first = await verifier.verify("toi di hoc", diacritic_candidates={"toi": ["tôi", "tối"]})
    second = await verifier.verify("toi di hoc", diacritic_candidates={"toi": ["tôi", "tối"]})

    assert first.verified_text == "toi di hoc"
    assert second.verified_text == "toi di hoc"
    assert second.from_cache is True
    assert client.calls == 1
