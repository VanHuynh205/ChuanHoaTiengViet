import asyncio
import pytest

from app.ai.client import AIRequest, AIResponse
from app.ai.disambiguator import (
    AmbiguityInput,
    ContextDisambiguationResult,
    ContextDisambiguator,
    _parse_disambiguation_response,
    _try_parse_json,
)


class FakeAIClient:
    def __init__(self, response_text: str = "", available: bool = True):
        self._response_text = response_text
        self._available = available
        self.calls: list[AIRequest] = []

    def is_available(self) -> bool:
        return self._available

    async def complete(self, request: AIRequest) -> AIResponse:
        self.calls.append(request)
        return AIResponse(text=self._response_text, model="fake", tokens_used=10, latency_ms=0)


class TestTryParseJson:
    def test_valid_json(self):
        result = _try_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_invalid_json(self):
        assert _try_parse_json("not json") is None

    def test_markdown_fenced_json(self):
        raw = '```json\n{"refined_text": "test"}\n```'
        result = _try_parse_json(raw)
        assert result == {"refined_text": "test"}

    def test_empty_string(self):
        assert _try_parse_json("") is None


class TestParseDisambiguationResponse:
    def test_valid_response(self):
        raw = '{"refined_text": "tôi đi học", "disambiguations": [{"abbr": "dk", "chosen": "đăng ký", "reason": "ngữ cảnh"}], "confidence": 0.95}'
        ambiguities = [AmbiguityInput(abbr="dk", options=["đăng ký", "đúng không"])]
        result = _parse_disambiguation_response(raw, "toi di hoc", ambiguities)
        assert result.refined_text == "tôi đi học"
        assert result.confidence == 0.95
        assert len(result.disambiguations) == 1
        assert result.disambiguations[0].abbr == "dk"
        assert result.disambiguations[0].chosen == "đăng ký"

    def test_invalid_json_returns_original(self):
        result = _parse_disambiguation_response("bad json", "original text", [])
        assert result.refined_text == "original text"
        assert result.confidence == 0.0
        assert result.disambiguations == []

    def test_filters_unknown_abbrs(self):
        raw = '{"refined_text": "test", "disambiguations": [{"abbr": "unknown", "chosen": "x", "reason": "y"}], "confidence": 0.8}'
        ambiguities = [AmbiguityInput(abbr="dk", options=["a", "b"])]
        result = _parse_disambiguation_response(raw, "test", ambiguities)
        assert result.disambiguations == []

    def test_handles_missing_fields(self):
        raw = '{"confidence": 0.7}'
        result = _parse_disambiguation_response(raw, "fallback text", [])
        assert result.refined_text == "fallback text"
        assert result.confidence == 0.7

    def test_skips_non_dict_disambiguations(self):
        raw = '{"refined_text": "ok", "disambiguations": ["not a dict", 42], "confidence": 0.5}'
        result = _parse_disambiguation_response(raw, "ok", [])
        assert result.disambiguations == []


class TestContextDisambiguator:
    def _run(self, coro):
        return asyncio.run(coro)

    def test_is_available_delegates_to_client(self):
        client = FakeAIClient(available=True)
        disambiguator = ContextDisambiguator(ai_client=client)
        assert disambiguator.is_available() is True

        client2 = FakeAIClient(available=False)
        disambiguator2 = ContextDisambiguator(ai_client=client2)
        assert disambiguator2.is_available() is False

    def test_disambiguate_calls_ai_and_parses(self):
        ai_response = '{"refined_text": "tôi đi đăng ký", "disambiguations": [{"abbr": "dk", "chosen": "đăng ký", "reason": "context"}], "confidence": 0.9}'
        client = FakeAIClient(response_text=ai_response)
        disambiguator = ContextDisambiguator(ai_client=client)

        ambiguities = [AmbiguityInput(abbr="dk", options=["đăng ký", "đúng không"])]
        result = self._run(disambiguator.disambiguate("toi di dk", ambiguities))

        assert result.refined_text == "tôi đi đăng ký"
        assert result.confidence == 0.9
        assert len(result.disambiguations) == 1
        assert result.from_cache is False
        assert len(client.calls) == 1

    def test_cached_result_returned_on_repeat(self):
        ai_response = '{"refined_text": "cached", "disambiguations": [], "confidence": 0.8}'
        client = FakeAIClient(response_text=ai_response)
        disambiguator = ContextDisambiguator(ai_client=client)

        r1 = self._run(disambiguator.disambiguate("text", []))
        r2 = self._run(disambiguator.disambiguate("text", []))

        assert r1.refined_text == "cached"
        assert r2.from_cache is True
        assert len(client.calls) == 1

    def test_no_ambiguities_still_works(self):
        ai_response = '{"refined_text": "tôi đi học", "disambiguations": [], "confidence": 0.95}'
        client = FakeAIClient(response_text=ai_response)
        disambiguator = ContextDisambiguator(ai_client=client)

        result = self._run(disambiguator.disambiguate("toi di hoc", []))
        assert result.refined_text == "tôi đi học"
        assert result.disambiguations == []

    def test_result_is_frozen(self):
        result = ContextDisambiguationResult(
            refined_text="test", disambiguations=[], confidence=0.9
        )
        with pytest.raises(AttributeError):
            result.confidence = 0.5
