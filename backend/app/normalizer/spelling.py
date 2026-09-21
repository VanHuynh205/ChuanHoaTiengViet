"""Versioned, conservative spelling corrections for contextual normalization."""

from __future__ import annotations
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Mapping
from app.utils.text_utils import protected_literal_spans


@lru_cache(maxsize=1)
def load_known_typos(data_dir: str) -> Mapping[str, dict]:
    path = Path(data_dir) / "spelling" / "known_typos.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {
        str(item["wrong"]): item
        for item in payload.get("entries", [])
        if item.get("wrong") and item.get("correct")
    }


def apply_known_spelling(text: str, data_dir: str) -> tuple[str, list[dict]]:
    """Exact seed matches only; title-case names and protected literals are excluded."""
    protected = protected_literal_spans(text)
    matches = []
    for wrong, entry in load_known_typos(data_dir).items():
        for match in re.finditer(rf"(?<!\w){re.escape(wrong)}(?!\w)", text):
            if any(start < match.end() and end > match.start() for start, end in protected):
                continue
            matches.append((match.start(), match.end(), str(entry["correct"])))
    parts, edits = [], []
    cursor = output_length = 0
    for start, end, replacement in sorted(matches):
        if start < cursor:
            continue
        parts.append(text[cursor:start])
        output_length += start - cursor
        edits.append(
            dict(
                originalStart=start,
                originalEnd=end,
                correctedStart=output_length,
                correctedEnd=output_length + len(replacement),
                replacement=replacement,
                kinds=["spelling"],
                reason="known_typo",
                confidence=0.99,
            )
        )
        parts.append(replacement)
        output_length += len(replacement)
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts), edits
