from __future__ import annotations

import unicodedata


def normalize_unicode(text: str) -> str:
    """Apply NFKC Unicode normalization to canonicalize Vietnamese diacritic composites.

    Runs first in the pipeline so all downstream steps work with a consistent encoding.
    """
    return unicodedata.normalize("NFKC", text)
