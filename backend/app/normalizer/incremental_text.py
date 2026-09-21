from __future__ import annotations

import re
from dataclasses import dataclass

_WORD_SPAN_RE = re.compile(r"\S+")
_SENTENCE_ENDINGS = (".", "!", "?", "\u2026")
_TRAILING_CLOSERS = "\"')]}>"


@dataclass(frozen=True)
class TextSegment:
    text: str
    start_word: int
    end_word: int
    leading_separator: str = ""
    trailing_separator: str = ""


def split_for_incremental_normalization(text: str, target_words: int) -> list[TextSegment]:
    """Split long text into stable sentence-aware chunks for cache reuse."""
    words = list(_WORD_SPAN_RE.finditer(text))
    if not words:
        return []

    max_words = max(1, target_words)
    if len(words) <= max_words:
        return [TextSegment(text=text, start_word=0, end_word=len(words))]

    segments: list[TextSegment] = []
    start_word = 0
    while start_word < len(words):
        hard_limit = min(start_word + max_words, len(words))
        split_word = hard_limit
        min_sentence_words = start_word + max(1, max_words // 2)

        for index in range(hard_limit - 1, min_sentence_words - 1, -1):
            if _ends_sentence(words[index].group(0)):
                split_word = index + 1
                break

        start_char = words[start_word].start()
        end_char = words[split_word - 1].end()
        segment_text = text[start_char:end_char]
        if segment_text:
            segments.append(
                TextSegment(
                    text=segment_text,
                    start_word=start_word,
                    end_word=split_word,
                    leading_separator=(
                        text[:start_char]
                        if not segments
                        else text[words[start_word - 1].end() : start_char]
                    ),
                    trailing_separator=text[end_char:] if split_word == len(words) else "",
                )
            )
        start_word = split_word

    return segments


def _ends_sentence(token: str) -> bool:
    return token.rstrip(_TRAILING_CLOSERS).endswith(_SENTENCE_ENDINGS)
