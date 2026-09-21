"""Heuristic detector for Vietnamese text that is missing diacritics.

The main entry point ``is_likely_no_diacritic`` returns ``True`` when a text
segment appears to be Vietnamese but has too few accented vowels relative to the
total vowel count.  This lets the pipeline decide whether to invoke the (more
expensive) diacritic restoration step.
"""

from __future__ import annotations

VOWELS_WITH_DIACRITIC = frozenset(
    "àáảãạăằắẳẵặâầấẩẫậ" "èéẻẽẹêềếểễệ" "ìíỉĩị" "òóỏõọôồốổỗộơờớởỡợ" "ùúủũụưừứửữự" "ỳýỷỹỵ" "đ"
)

VOWELS_WITHOUT_DIACRITIC = frozenset("aeiouy")

ALL_VOWELS = VOWELS_WITH_DIACRITIC | VOWELS_WITHOUT_DIACRITIC


def _count_vowels(text: str) -> tuple[int, int]:
    """Return (with_diacritic_count, total_vowel_count)."""
    with_diacritic = 0
    total = 0
    for ch in text.lower():
        if ch in ALL_VOWELS:
            total += 1
            if ch in VOWELS_WITH_DIACRITIC:
                with_diacritic += 1
    return with_diacritic, total


def _has_enough_alpha(text: str, min_alpha_ratio: float = 0.3) -> bool:
    """Check that the text has a minimum proportion of alphabetic characters."""
    if not text:
        return False
    alpha_count = sum(1 for ch in text if ch.isalpha())
    return alpha_count / len(text) >= min_alpha_ratio


def is_likely_no_diacritic(
    text: str,
    threshold: float = 0.6,
    min_length: int = 8,
) -> bool:
    """Return ``True`` when *text* looks like Vietnamese without diacritics.

    Parameters
    ----------
    text:
        The input string to check.
    threshold:
        If the ratio ``diacritics / total_vowels`` is **below** this number,
        the text is considered to be missing diacritics.  Default ``0.6`` means
        that fewer than 60 % of vowels carry accents.
    min_length:
        Texts shorter than this are skipped (too little signal).

    Returns
    -------
    bool
        ``True`` when the text is long enough, has enough alphabetic content,
        and the diacritic ratio is below *threshold*.
    """
    stripped = text.strip()
    if len(stripped) < min_length:
        return False

    if not _has_enough_alpha(stripped):
        return False

    with_diacritic, total_vowels = _count_vowels(stripped)
    if total_vowels == 0:
        return False

    ratio = with_diacritic / total_vowels
    return ratio < threshold
