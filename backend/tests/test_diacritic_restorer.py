import asyncio
import json
import pytest

from app.config import Settings
from app.normalizer.diacritic_restorer import (
    DiacriticRestorer,
    SyncDiacriticRestorer,
    SyncDiacriticResult,
    _rule_restore,
    _diff_tokens,
    _parse_ai_response,
    get_shared_context_phrase_overrides,
    get_shared_word_map,
    load_bigram_freq,
    load_context_phrase_overrides,
    load_word_map,
    load_few_shot_examples,
)
from app.ai.client import AIRequest, AIResponse


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


SAMPLE_WORD_MAP = {
    "toi": ["tôi"],
    "di": ["đi"],
    "hoc": ["học"],
    "moi": ["mỗi", "mới"],
    "ngay": ["ngày"],
    "o": ["ở"],
    "truong": ["trường"],
    "khong": ["không"],
}


class TestRuleRestore:
    def test_basic_restoration(self):
        text = "toi di hoc"
        restored, changed, coverage, ambiguous = _rule_restore(text, SAMPLE_WORD_MAP)
        assert restored == "tôi đi học"
        assert len(changed) == 3
        assert coverage == 1.0
        assert ambiguous == {}

    def test_empty_text(self):
        restored, changed, coverage, _ = _rule_restore("", SAMPLE_WORD_MAP)
        assert restored == ""
        assert changed == []
        assert coverage == 1.0

    def test_unknown_words_reduce_coverage(self):
        text = "toi thich xuan bao"
        restored, changed, coverage, _ = _rule_restore(text, SAMPLE_WORD_MAP)
        assert "tôi" in restored
        assert coverage < 1.0

    def test_capitalization_preserved(self):
        text = "Toi di hoc"
        restored, changed, _, _ = _rule_restore(text, SAMPLE_WORD_MAP)
        assert restored.startswith("Tôi")

    def test_punctuation_preserved(self):
        text = "toi di hoc."
        restored, changed, _, _ = _rule_restore(text, SAMPLE_WORD_MAP)
        assert restored == "tôi đi học."

    def test_whitespace_layout_is_preserved(self):
        restored, _, _, _ = _rule_restore("toi  di\n\nhoc", SAMPLE_WORD_MAP)
        assert restored == "tôi  đi\n\nhọc"

    def test_empty_word_map(self):
        text = "toi di hoc"
        restored, changed, coverage, _ = _rule_restore(text, {})
        assert restored == text
        assert changed == []

    def test_already_has_diacritics(self):
        text = "tôi đi học"
        restored, changed, _, _ = _rule_restore(text, SAMPLE_WORD_MAP)
        assert changed == []

    def test_uppercase_acronym_without_diacritics_is_preserved(self):
        restored, changed, _, _ = _rule_restore("AI tot", {"ai": ["ai"], "tot": ["tốt"]})
        assert restored == "AI tốt"
        assert ("AI", "Ai") not in changed


    def test_context_phrase_overrides_multiword_ambiguity(self):
        restored, changed, coverage, _ = _rule_restore(
            "toi lam do an co so",
            {"toi": ["t\u00f4i"], "lam": ["l\u00e0m"]},
            context_phrases={
                ("do", "an", "co", "so"): ("\u0111\u1ed3", "\u00e1n", "c\u01a1", "s\u1edf")
            },
        )

        assert restored == "t\u00f4i l\u00e0m \u0111\u1ed3 \u00e1n c\u01a1 s\u1edf"
        assert ("do", "\u0111\u1ed3") in changed
        assert coverage == 1.0


class TestDiffTokens:
    def test_detects_changes(self):
        changed = _diff_tokens("toi di hoc", "tôi đi học")
        assert len(changed) == 3
        assert ("toi", "tôi") in changed

    def test_no_changes(self):
        assert _diff_tokens("hello world", "hello world") == []

    def test_mismatched_lengths(self):
        changed = _diff_tokens("a b", "a b c")
        assert len(changed) == 0


class TestParseAIResponse:
    def test_valid_json(self):
        raw = '{"restored": "tôi đi học", "confidence": "0.95"}'
        result = _parse_ai_response(raw, "toi di hoc")
        assert result["restored"] == "tôi đi học"

    def test_markdown_fenced_json(self):
        raw = '```json\n{"restored": "tôi đi học", "confidence": "0.9"}\n```'
        result = _parse_ai_response(raw, "toi di hoc")
        assert result["restored"] == "tôi đi học"

    def test_invalid_json_returns_original(self):
        result = _parse_ai_response("not json at all", "toi di hoc")
        assert result["restored"] == "toi di hoc"

    def test_valid_json_that_is_not_an_object_returns_original(self):
        # Regression: a bare list/string used to raise AttributeError past the
        # AIError fallback instead of degrading to the rule-based result.
        for raw in ('["x"]', '"just a string"', "42"):
            result = _parse_ai_response(raw, "toi di hoc")
            assert result["restored"] == "toi di hoc"
            assert float(result["confidence"]) == 0.0

    def test_null_or_non_numeric_confidence_degrades_to_zero(self):
        # Regression: confidence null used to become the string "None" and
        # crash float() at the call site.
        result = _parse_ai_response('{"restored": "tôi đi học", "confidence": null}', "x")
        assert result["restored"] == "tôi đi học"
        assert float(result["confidence"]) == 0.0
        result = _parse_ai_response('{"restored": "tôi đi học", "confidence": "cao"}', "x")
        assert float(result["confidence"]) == 0.0


class TestLoadWordMap:
    def test_nonexistent_path(self, tmp_path):
        result = load_word_map(tmp_path / "missing.json")
        assert result == {}

    def test_valid_file(self, tmp_path):
        import json

        path = tmp_path / "map.json"
        path.write_text(json.dumps({"toi": ["tôi"], "di": "đi"}), encoding="utf-8")
        result = load_word_map(path)
        assert result["toi"] == ["tôi"]
        assert result["di"] == ["đi"]


class TestLoadBigramFreq:
    def test_nonexistent_path(self, tmp_path):
        result = load_bigram_freq(tmp_path / "missing.json")
        assert result == {}

    def test_valid_file_casts_counts_to_int(self, tmp_path):
        import json

        path = tmp_path / "bigram.json"
        path.write_text(json.dumps({"nghe_noi": "3"}), encoding="utf-8")
        result = load_bigram_freq(path)
        assert result == {"nghe_noi": 3}


class TestLoadFewShot:
    def test_nonexistent_path(self, tmp_path):
        result = load_few_shot_examples(tmp_path / "missing.json")
        assert result == []

    def test_limits_count(self, tmp_path):
        import json

        examples = [{"input": f"ex{i}", "output": f"out{i}"} for i in range(20)]
        path = tmp_path / "examples.json"
        path.write_text(json.dumps(examples), encoding="utf-8")
        result = load_few_shot_examples(path, count=3)
        assert len(result) == 3


class TestLoadContextPhraseOverrides:
    def test_nonexistent_path(self, tmp_path):
        result = load_context_phrase_overrides(tmp_path / "missing.json")
        assert result == {}

    def test_valid_file_keeps_multiword_same_length_phrases(self, tmp_path):
        path = tmp_path / "context_phrases.json"
        path.write_text(
            json.dumps(
                {
                    "do an co so": "\u0111\u1ed3 \u00e1n c\u01a1 s\u1edf",
                    "single": "m\u1ed9t",
                    "bad length": "h\u1ecfng",
                    "": "",
                }
            ),
            encoding="utf-8",
        )

        result = load_context_phrase_overrides(path)

        assert result == {
            ("do", "an", "co", "so"): ("\u0111\u1ed3", "\u00e1n", "c\u01a1", "s\u1edf")
        }


class TestSyncDiacriticRestorer:
    def test_restores_no_diacritic_text(self):
        restorer = SyncDiacriticRestorer(word_map=SAMPLE_WORD_MAP)
        result = restorer.restore("toi di hoc moi ngay o truong")
        assert result.applied is True
        assert "tôi" in result.restored_text
        assert "đi" in result.restored_text
        assert "học" in result.restored_text
        assert len(result.changed_tokens) > 0

    def test_skips_text_with_diacritics(self):
        restorer = SyncDiacriticRestorer(word_map=SAMPLE_WORD_MAP)
        result = restorer.restore("Tôi đi học mỗi ngày ở trường")
        assert result.applied is False
        assert result.changed_tokens == []
        assert result.restored_text == "Tôi đi học mỗi ngày ở trường"

    def test_skips_short_text(self):
        restorer = SyncDiacriticRestorer(word_map=SAMPLE_WORD_MAP, min_text_length=20)
        result = restorer.restore("toi di hoc")
        assert result.applied is False

    def test_custom_threshold(self):
        restorer = SyncDiacriticRestorer(word_map=SAMPLE_WORD_MAP, detection_threshold=0.99)
        result = restorer.restore("toi di hoc moi ngay o truong")
        assert result.applied is True

    def test_empty_word_map_no_changes(self):
        # No word map AND no context phrases -> nothing to restore with.
        # (Built-in context phrases are word-map independent and would still
        # legitimately change known collocations like "moi ngay".)
        restorer = SyncDiacriticRestorer(word_map={}, context_phrases={})
        result = restorer.restore("toi di hoc moi ngay o truong")
        assert result.applied is False
        assert result.changed_tokens == []

    def test_result_is_frozen(self):
        restorer = SyncDiacriticRestorer(word_map=SAMPLE_WORD_MAP)
        result = restorer.restore("toi di hoc")
        assert isinstance(result, SyncDiacriticResult)
        with pytest.raises(AttributeError):
            result.applied = False


class TestGetSharedWordMap:
    def test_loads_from_data_dir(self, tmp_path):
        import json

        diacritic_dir = tmp_path / "diacritic"
        diacritic_dir.mkdir()
        map_file = diacritic_dir / "word_map.json"
        map_file.write_text(json.dumps({"xin": ["xin"], "chao": ["chào"]}), encoding="utf-8")
        import app.normalizer.diacritic_restorer as mod

        original = mod._SHARED_WORD_MAP
        try:
            mod._SHARED_WORD_MAP = None
            result = get_shared_word_map(tmp_path)
            assert "chao" in result
            assert result["chao"] == ["chào"]
        finally:
            mod._SHARED_WORD_MAP = original

    def test_returns_builtin_entries_for_missing_file(self, tmp_path):
        import app.normalizer.diacritic_restorer as mod

        original = mod._SHARED_WORD_MAP
        try:
            mod._SHARED_WORD_MAP = None
            result = get_shared_word_map(tmp_path)
            # With no generated word map the built-in chat entries still apply
            # ("met"/"thi"/... would otherwise be permanently unrestorable).
            assert result == mod._BUILTIN_WORD_MAP_ENTRIES
        finally:
            mod._SHARED_WORD_MAP = original


class TestGetSharedContextPhraseOverrides:
    def test_loads_file_and_preserves_builtin_precedence(self, tmp_path):
        diacritic_dir = tmp_path / "diacritic"
        diacritic_dir.mkdir()
        phrase_file = diacritic_dir / "context_phrases.json"
        phrase_file.write_text(
            json.dumps(
                {
                    "do an co so": "\u0111\u1ed3 \u00e1n c\u01a1 s\u1edf",
                    "that day": "sai sai",
                }
            ),
            encoding="utf-8",
        )
        import app.normalizer.diacritic_restorer as mod

        original = mod._SHARED_CONTEXT_PHRASE_OVERRIDES
        try:
            mod._SHARED_CONTEXT_PHRASE_OVERRIDES = None
            result = get_shared_context_phrase_overrides(tmp_path)
            assert result[("do", "an", "co", "so")] == (
                "\u0111\u1ed3",
                "\u00e1n",
                "c\u01a1",
                "s\u1edf",
            )
            assert result[("that", "day")] == ("th\u1eadt", "\u0111\u1ea5y")
        finally:
            mod._SHARED_CONTEXT_PHRASE_OVERRIDES = original


class TestDiacriticRestorer:
    def _run(self, coro):
        return asyncio.run(coro)

    def test_skip_when_already_has_diacritics(self, tmp_path):
        settings = Settings(data_dir=tmp_path)
        client = FakeAIClient()
        restorer = DiacriticRestorer(
            settings=settings,
            ai_client=client,
            word_map=SAMPLE_WORD_MAP,
            few_shot_examples=[],
        )
        result = self._run(restorer.restore("Tôi đi học mỗi ngày ở trường"))
        assert result.engine == "skip"
        assert result.restored_text == "Tôi đi học mỗi ngày ở trường"

    def test_force_bypasses_detection(self, tmp_path):
        settings = Settings(data_dir=tmp_path)
        client = FakeAIClient(available=False)
        restorer = DiacriticRestorer(
            settings=settings,
            ai_client=client,
            word_map=SAMPLE_WORD_MAP,
            few_shot_examples=[],
        )
        result = self._run(restorer.restore("Tôi đi học mỗi ngày ở trường", force=True))
        assert result.engine == "rule"

    def test_rule_based_high_coverage(self, tmp_path):
        settings = Settings(data_dir=tmp_path)
        client = FakeAIClient(available=False)
        restorer = DiacriticRestorer(
            settings=settings,
            ai_client=client,
            word_map=SAMPLE_WORD_MAP,
            few_shot_examples=[],
        )
        result = self._run(restorer.restore("toi di hoc moi ngay"))
        assert result.engine == "rule"
        assert result.restored_text == "tôi đi học mỗi ngày"
        assert len(result.changed_tokens) == 5

    def test_rule_based_uses_bigram_context(self, tmp_path):
        settings = Settings(data_dir=tmp_path)
        client = FakeAIClient(available=False)
        restorer = DiacriticRestorer(
            settings=settings,
            ai_client=client,
            word_map={
                "nghe": ["nghe", "ngh\u1ec7"],
                "thuat": ["thu\u1eadt"],
            },
            bigram_freq={"ngh\u1ec7_thu\u1eadt": 10},
            few_shot_examples=[],
        )
        result = self._run(restorer.restore("nghe thuat"))
        assert result.engine == "rule"
        assert result.restored_text == "ngh\u1ec7 thu\u1eadt"

    def test_ai_fallback_on_low_coverage(self, tmp_path):
        settings = Settings(data_dir=tmp_path)
        ai_response = '{"restored": "tôi thích ăn phở", "confidence": "0.92"}'
        client = FakeAIClient(response_text=ai_response, available=True)
        restorer = DiacriticRestorer(
            settings=settings,
            ai_client=client,
            word_map={},
            few_shot_examples=[{"input": "x", "output": "y"}],
        )
        result = self._run(restorer.restore("toi thich an pho"))
        assert result.engine in ("ai", "hybrid")
        assert result.restored_text == "tôi thích ăn phở"
        assert len(client.calls) == 1

    def test_cache_returns_cached_result(self, tmp_path):
        settings = Settings(data_dir=tmp_path)
        client = FakeAIClient(available=False)
        restorer = DiacriticRestorer(
            settings=settings,
            ai_client=client,
            word_map=SAMPLE_WORD_MAP,
            few_shot_examples=[],
        )
        r1 = self._run(restorer.restore("toi di hoc moi ngay"))
        r2 = self._run(restorer.restore("toi di hoc moi ngay"))
        assert r1.restored_text == r2.restored_text
        assert r2.engine == "rule"

    def test_result_has_latency(self, tmp_path):
        settings = Settings(data_dir=tmp_path)
        client = FakeAIClient(available=False)
        restorer = DiacriticRestorer(
            settings=settings,
            ai_client=client,
            word_map=SAMPLE_WORD_MAP,
            few_shot_examples=[],
        )
        result = self._run(restorer.restore("toi di hoc moi ngay"))
        assert result.latency_ms >= 0
