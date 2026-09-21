"""Conservative v1: a single question mark for explicit question openings."""

import re
import unicodedata
from difflib import SequenceMatcher
from app.utils.text_utils import protected_literal_spans

# Deliberately exclude 'ai' and 'gì': 'ai cũng ...' is not a question.
OPENING = re.compile(r"^(?:tại sao|vì sao|bao giờ|bao nhiêu)\s+\S", re.IGNORECASE)


def restore_terminal_punctuation(source: str, output: str) -> str:
    """Restore an existing separator lost while a phrase/abbreviation expanded.

    Only punctuation-only source edits are eligible; never guess punctuation at
    a deleted word or manufacture a new separator. Source must be emoji-cleaned.
    """

    def folded(text: str) -> str:
        parts = []
        for char in text:
            part = "".join(
                c
                for c in unicodedata.normalize("NFD", char.lower())
                if unicodedata.category(c) != "Mn"
            ).replace("đ", "d")
            parts.append(part if len(part) == 1 else char)
        return "".join(parts)

    edits = []
    for tag, a, b, c, d in SequenceMatcher(
        None, folded(source), folded(output), autojunk=False
    ).get_opcodes():
        fragment = source[a:b].strip()
        if (
            tag not in {"delete", "replace"}
            or not fragment
            or any(char not in ",.;:!?…" for char in fragment)
        ):
            continue
        if not any(char in ",.;:!?…" for char in output[c:d]):
            edits.append((d, fragment))
    for position, fragment in reversed(edits):
        output = output[:position] + fragment + output[position:]
    return output


def preserves_punctuation(source: str, output: str) -> bool:
    """AI may resolve words, but may not add/remove/reorder punctuation."""

    def marks(value: str) -> list[str]:
        return [c for c in value if unicodedata.category(c).startswith("P")]

    return marks(source) == marks(output)


def append_question_mark(text: str) -> tuple[str, dict | None]:
    end = len(text.rstrip())
    line_start = text.rfind("\n", 0, end) + 1
    line = text[line_start:end].strip()
    if not OPENING.match(line):
        return text, None
    # Refuse punctuation, numbers and literals rather than editing their syntax.
    if protected_literal_spans(line) or any(
        c.isdigit() or unicodedata.category(c)[0] in {"P", "S"} for c in line
    ):
        return text, None
    return text[:end] + "?" + text[end:], dict(
        kinds=["punctuation"],
        reason="explicit_question_opening",
        originalStart=end,
        originalEnd=end,
        outputStart=end,
        outputEnd=end + 1,
        originalText="",
        outputText="?",
    )
