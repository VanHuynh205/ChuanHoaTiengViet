from __future__ import annotations

import re
from collections.abc import Container

THREE_PLUS_REPEATS = re.compile(r"([a-zA-ZÀ-ỹ])\1{2,}", re.UNICODE)
ONE_PLUS_REPEATS = re.compile(r"([a-zA-ZÀ-ỹ])\1{1,}", re.UNICODE)


def reduce_repeated_characters(word: str) -> str:
    return THREE_PLUS_REPEATS.sub(r"\1", word)


def normalize_elongated_word(
    word: str,
    known_words: Container[str],
    known_abbreviations: Container[str],
) -> str:
    lowered = word.lower()
    if lowered in known_words or lowered in known_abbreviations:
        return word

    reduced = reduce_repeated_characters(word)
    reduced_lower = reduced.lower()
    if reduced_lower in known_words or reduced_lower in known_abbreviations:
        return reduced

    fully_reduced = ONE_PLUS_REPEATS.sub(r"\1", word)
    fully_reduced_lower = fully_reduced.lower()
    if fully_reduced_lower in known_words or fully_reduced_lower in known_abbreviations:
        return fully_reduced

    return reduced
