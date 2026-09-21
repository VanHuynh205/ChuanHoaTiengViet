from __future__ import annotations

from typing import Dict


def expand_abbreviation(word: str, abbreviations: Dict[str, str]) -> str:
    """Return the expanded form of a single token, or the token unchanged if not found.

    Phase 2 will extend this with phrase-level matching before token-level lookup.
    """
    return abbreviations.get(word.lower(), word)
