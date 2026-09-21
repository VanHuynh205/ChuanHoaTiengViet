from app.utils.text_utils import (
    capitalize_sentence_starts,
    join_scan_tokens,
    protected_literal_spans,
    tokenize_for_scan,
)


def test_capitalize_sentence_starts_capitalizes_first_word_and_after_punctuation():
    text = "toi di hoc. hom nay troi dep! ban di khong?"

    result = capitalize_sentence_starts(text)

    assert result == "Toi di hoc. Hom nay troi dep! Ban di khong?"


def test_capitalize_sentence_starts_handles_quotes_and_keeps_existing_case():
    text = '"toi dung NVIDIA GPU." ai cung biet OpenAI.'

    result = capitalize_sentence_starts(text)

    assert result == '"Toi dung NVIDIA GPU." Ai cung biet OpenAI.'


def test_tokenizer_never_drops_characters():
    """Round-tripping must be lossless for content the product actually sees.

    The old pattern silently deleted CJK characters, underscores and every line
    break, so the "copy result" button handed the user mangled text.
    """
    samples = [
        "toi thich 日本 lam",
        "ma don 100_000 nhe",
        "abc_def@gmail.com",
        "xem https://vd.com/a?b=1 nhe",
        "dong mot\ndong hai",
        "doan mot\n\ndoan hai",
        "chao ban, khoe khong?",
    ]
    for sample in samples:
        assert join_scan_tokens(tokenize_for_scan(sample)) == sample, sample


def test_line_breaks_are_their_own_token_and_do_not_gain_a_space():
    assert tokenize_for_scan("a\nb") == ["a", "\n", "b"]
    assert join_scan_tokens(["a", "\n", "b"]) == "a\nb"


def test_protected_literal_spans_cover_urls_code_and_numeric_expressions():
    text = "https://example.com C++ C# 9/10 50% NVIDIA OpenAI"
    spans = protected_literal_spans(text)

    assert [text[start:end] for start, end in spans] == [
        "https://example.com",
        "C++",
        "C#",
        "9/10",
        "50%",
        "NVIDIA",
        "OpenAI",
    ]
