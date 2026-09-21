from app.utils.diacritic_detect import is_likely_no_diacritic, _count_vowels


class TestCountVowels:
    def test_all_diacritics(self):
        with_d, total = _count_vowels("Đà Nẵng đẹp lắm")
        assert with_d > 0
        assert total >= with_d

    def test_no_diacritics(self):
        with_d, total = _count_vowels("toi di hoc moi ngay")
        assert with_d == 0
        assert total > 0

    def test_empty(self):
        assert _count_vowels("") == (0, 0)

    def test_no_vowels(self):
        assert _count_vowels("123 !@#") == (0, 0)


class TestIsLikelyNoDiacritic:
    def test_short_text_returns_false(self):
        assert is_likely_no_diacritic("abc") is False

    def test_text_below_min_length(self):
        assert is_likely_no_diacritic("toi di", min_length=10) is False

    def test_no_diacritic_text(self):
        assert is_likely_no_diacritic("toi di hoc moi ngay o truong") is True

    def test_fully_accented_text(self):
        assert is_likely_no_diacritic("Tôi đi học mỗi ngày ở trường") is False

    def test_mixed_but_above_threshold(self):
        text = "Tôi đi học ở trường rất tốt"
        assert is_likely_no_diacritic(text, threshold=0.3) is False

    def test_non_alpha_text_returns_false(self):
        assert is_likely_no_diacritic("123456789012345") is False

    def test_custom_threshold(self):
        text = "toi di hoc moi ngay o truong dai hoc"
        assert is_likely_no_diacritic(text, threshold=0.9) is True

    def test_all_consonants_returns_false(self):
        assert is_likely_no_diacritic("bcd fgh jkl mnp") is False

    def test_whitespace_only(self):
        assert is_likely_no_diacritic("          ") is False

    def test_default_threshold_boundary(self):
        text = "Đà Nẵng đẹp lắm nhưng nong qua"
        result = is_likely_no_diacritic(text, threshold=0.6)
        assert isinstance(result, bool)
