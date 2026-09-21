from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Pattern

EMOJI_DATA_FILE = "emoji-test.json"
EMOJI_DIR_NAME = "Emoji"
_REMOVED_MARKER = "\ue000"
EMOTICON_PATTERN = re.compile(
    r"(?<!\w)(?:"
    r":-?\)+|:-?\(+|;-?\)+|;-?\(+|"
    r":-D|:D|=D|:-P|:P|:-p|:p|:-V|:V|:-v|:v|"
    r"=\)+|\^_\^|\^\^|T_T|t_t|-_-|\._\.|"
    r":'\)|:'\(|<3"
    r")(?!\w)"
)


@dataclass(frozen=True)
class EmojiRemovalResult:
    cleaned_text: str
    removed_any: bool


def remove_emoji_and_emoticons(text: str, data_dir: Path) -> EmojiRemovalResult:
    removed_text = text
    removed_any = False

    emoji_pattern = _load_emoji_pattern(str(Path(data_dir).resolve()))
    if emoji_pattern is not None:
        removed_text, emoji_count = emoji_pattern.subn(_REMOVED_MARKER, removed_text)
        removed_any = removed_any or emoji_count > 0

    removed_text, emoticon_count = EMOTICON_PATTERN.subn(_REMOVED_MARKER, removed_text)
    removed_any = removed_any or emoticon_count > 0

    if not removed_any:
        return EmojiRemovalResult(cleaned_text=text, removed_any=False)

    return EmojiRemovalResult(
        cleaned_text=_restore_removed_spacing(removed_text),
        removed_any=True,
    )


def _restore_removed_spacing(text: str) -> str:
    """Remove markers while keeping paragraph breaks and one meaningful separator."""
    marker_pattern = re.compile(
        rf"(?P<left>[ \t]*){re.escape(_REMOVED_MARKER)}+(?P<right>[ \t]*)"
    )

    def replace(match: re.Match[str]) -> str:
        start, end = match.span()
        left_neighbor = text[start - 1] if start > 0 else ""
        right_neighbor = text[end] if end < len(text) else ""
        if left_neighbor in "\r\n" or right_neighbor in "\r\n":
            return ""
        left = match.group("left")
        right = match.group("right")
        if left or right:
            return left or right
        return " "

    restored = marker_pattern.sub(replace, text)
    if not restored.strip() and not any(char in "\r\n" for char in restored):
        return ""
    return restored


@lru_cache(maxsize=None)
def _load_emoji_pattern(data_dir: str) -> Pattern[str] | None:
    emoji_file = Path(data_dir) / EMOJI_DIR_NAME / EMOJI_DATA_FILE
    if not emoji_file.exists():
        return None

    try:
        payload = json.loads(emoji_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    entries = payload.get("entries", [])
    emojis = sorted(
        {
            entry.get("emoji", "")
            for entry in entries
            if isinstance(entry, dict) and entry.get("emoji")
        },
        key=len,
        reverse=True,
    )
    if not emojis:
        return None

    return re.compile("|".join(re.escape(emoji) for emoji in emojis))
