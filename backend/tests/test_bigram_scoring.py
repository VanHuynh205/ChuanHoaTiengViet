"""Tests for context scoring in diacritic restoration."""

from __future__ import annotations

from app.normalizer.diacritic_restorer import (
    _rule_restore,
    _score_with_bigrams,
    collect_ambiguous_diacritics,
)


class TestScoreWithBigrams:
    """Unit tests for ``_score_with_bigrams``."""

    def test_picks_candidate_with_highest_bigram_score(self):
        candidates = ["ngh\u1ec7", "nghe", "ngh\u00e8"]
        bigram = {"nghe_n\u00f3i": 10, "ngh\u1ec7_thu\u1eadt": 16}
        result = _score_with_bigrams(candidates, None, ["n\u00f3i"], bigram)
        assert result == "nghe"

    def test_prefers_bigram_pair_over_frequency_default(self):
        candidates = ["chuy\u1ec7n", "chuy\u1ec1n", "chuy\u00ean", "chuy\u1ebfn"]
        bigram = {"chuy\u1ec1n_t\u00ecnh": 7, "chuy\u1ec7n_\u0111\u1ebfn": 2}
        result = _score_with_bigrams(candidates, None, ["t\u00ecnh"], bigram)
        assert result == "chuy\u1ec1n"

    def test_falls_back_to_first_when_no_bigram_match(self):
        candidates = ["\u0111\u00e3", "\u0111\u1ea1", "\u0111\u00e0"]
        bigram = {"nghe_n\u00f3i": 10}
        result = _score_with_bigrams(candidates, ["xyz"], ["abc"], bigram)
        assert result == "\u0111\u00e3"

    def test_falls_back_when_bigram_empty(self):
        candidates = ["chuy\u1ec7n", "chuy\u1ec1n"]
        result = _score_with_bigrams(candidates, ["v\u1eeba"], ["chia"], {})
        assert result == "chuy\u1ec7n"

    def test_considers_both_prev_and_next_word(self):
        candidates = ["ngh\u1ec7", "nghe"]
        bigram = {"nghe_n\u00f3i": 5, "t\u00f4i_nghe": 3}
        result = _score_with_bigrams(candidates, ["t\u00f4i"], ["n\u00f3i"], bigram)
        assert result == "nghe"

    def test_single_candidate_returns_it(self):
        candidates = ["ch\u1eafc"]
        bigram = {"nghe_n\u00f3i": 10}
        result = _score_with_bigrams(candidates, ["r\u1ea5t"], ["ch\u1eafn"], bigram)
        assert result == "ch\u1eafc"


class TestRuleRestoreWithContext:
    """Integration tests for ``_rule_restore`` with local context."""

    WORD_MAP = {
        "nghe": ["ngh\u1ec7", "nghe", "ngh\u00e8"],
        "noi": ["n\u1ed9i", "n\u00f3i", "n\u1ed5i"],
        "dao": ["\u0111\u1ea1o", "\u0111\u1ea3o", "\u0111\u00e0o", "dao"],
        "nay": ["n\u00e0y", "nay"],
        "on": ["\u1ed5n", "\u01a1n"],
        "ha": ["h\u00e0", "h\u1ea3"],
        "thuat": ["thu\u1eadt"],
        "chuyen": ["chuy\u1ec7n", "chuy\u1ec1n", "chuy\u00ean", "chuy\u1ebfn"],
        "tinh": ["t\u00ecnh", "t\u00ednh", "t\u1ec9nh"],
    }

    def test_common_chat_phrase_uses_curated_context(self):
        text = "nghe noi dao nay k on ha."
        result, changed, cov, ambig = _rule_restore(text, self.WORD_MAP)
        assert result == "nghe n\u00f3i d\u1ea1o n\u00e0y k \u1ed5n h\u1ea3."
        assert ("noi", "n\u00f3i") in changed
        assert cov > 0.8
        assert "nghe" in ambig

    def test_student_chat_phrase_uses_curated_context(self):
        text = "mon do an co so nay kho that day m a, phai thuc den tan khuya"
        result, changed, cov, _ = _rule_restore(text, self.WORD_MAP)

        assert (
            result
            == "m\u00f4n \u0111\u1ed3 \u00e1n c\u01a1 s\u1edf n\u00e0y kh\u00f3 th\u1eadt \u0111\u1ea5y m \u00e0, ph\u1ea3i th\u1ee9c \u0111\u1ebfn t\u1eadn khuya"
        )
        assert ("that", "th\u1eadt") in changed
        assert ("day", "\u0111\u1ea5y") in changed
        assert cov > 0.8

    def test_nghe_noi_without_bigrams_uses_curated_context(self):
        text = "nghe noi"
        result, changed, cov, ambig = _rule_restore(text, self.WORD_MAP)
        assert result == "nghe n\u00f3i"
        assert cov == 1.0
        assert "noi" in ambig

    def test_noi_cho_uses_curated_speech_context(self):
        text = "noi cho"
        word_map = {"noi": ["n\u1ed9i", "n\u00f3i"]}
        bigram = {"n\u00f3i_cho": 12}
        result, changed, cov, ambig = _rule_restore(text, word_map, bigram)
        assert result == "n\u00f3i cho"
        assert ("noi", "n\u00f3i") in changed
        assert cov == 1.0
        assert ambig == {"noi": ["n\u1ed9i", "n\u00f3i"]}

    def test_bigram_context_can_use_plain_neighbor_tokens(self):
        text = "ve nha"
        word_map = {"ve": ["v\u1ebd", "v\u1ec1"]}
        bigram = {"v\u1ec1_nha": 12}
        result, changed, cov, ambig = _rule_restore(text, word_map, bigram)
        assert result == "v\u1ec1 nha"
        assert ("ve", "v\u1ec1") in changed
        assert cov == 0.5
        assert ambig == {"ve": ["v\u1ebd", "v\u1ec1"]}

    def test_nghe_before_common_abbreviation_keeps_listen_meaning(self):
        text = "T nghe mn ban tan"
        word_map = {
            "nghe": ["ngh\u1ec7", "nghe"],
            "ban": ["b\u00e0n"],
            "tan": ["t\u00e1n"],
        }
        result, changed, cov, ambig = _rule_restore(text, word_map)
        assert result == "T nghe mn b\u00e0n t\u00e1n"
        assert ("nghe", "ngh\u1ec7") not in changed
        assert "nghe" in ambig

    def test_nghe_thuat_with_bigrams_picks_nghe_thuat(self):
        text = "nghe thuat"
        bigram = {"ngh\u1ec7_thu\u1eadt": 16}
        result, changed, cov, ambig = _rule_restore(text, self.WORD_MAP, bigram)
        assert result == "ngh\u1ec7 thu\u1eadt"

    def test_chuyen_tinh_with_bigrams(self):
        text = "chuyen tinh"
        bigram = {"chuy\u1ec1n_t\u00ecnh": 7, "chuy\u1ec7n_t\u00ecnh": 0}
        result, changed, cov, ambig = _rule_restore(text, self.WORD_MAP, bigram)
        assert "chuy\u1ec1n" in result

    def test_ambiguous_map_returned(self):
        text = "nghe noi"
        _, _, _, ambig = _rule_restore(text, self.WORD_MAP)
        assert "nghe" in ambig
        assert "noi" in ambig
        assert len(ambig["nghe"]) > 1

    def test_no_ambiguity_for_single_candidate(self):
        text = "thuat"
        _, _, _, ambig = _rule_restore(text, self.WORD_MAP)
        assert "thuat" not in ambig


class TestCollectAmbiguousDiacritics:
    """Tests for ``collect_ambiguous_diacritics``."""

    WORD_MAP = {
        "nghe": ["ngh\u1ec7", "nghe"],
        "noi": ["n\u1ed9i", "n\u00f3i"],
        "chac": ["ch\u1eafc"],
    }

    def test_returns_ambiguous_tokens_only(self):
        result = collect_ambiguous_diacritics("nghe noi chac", self.WORD_MAP)
        assert "nghe" in result
        assert "noi" in result
        assert "chac" not in result

    def test_handles_punctuation(self):
        result = collect_ambiguous_diacritics("nghe, noi.", self.WORD_MAP)
        assert "nghe" in result

    def test_empty_text(self):
        result = collect_ambiguous_diacritics("", self.WORD_MAP)
        assert result == {}
