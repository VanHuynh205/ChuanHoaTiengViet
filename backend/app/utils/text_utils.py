from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable, List

WORD_PATTERN = re.compile(r"[a-zA-ZÀ-ỹ]+", re.UNICODE)
# Token classes, in priority order:
#   1. URLs and e-mail addresses, kept whole so they are never re-spaced
#   2. Latin/Vietnamese words, digits and underscores  ("dk", "100_000")
#   3. CJK / Hangul runs, kept as one token
#   4. Line breaks, kept as their own token so paragraph structure survives
#   5. Punctuation and symbols
#   6. Catch-all for any other non-space character (Cyrillic, symbols, …)
# Before (1), (3), (4) and (6) the tokenizer silently DELETED characters: a chat
# message containing "日本" or a line break came back with that content missing,
# and "abc_def@gmail.com" was rewritten as "abc def@ gmail. com".
_URL_OR_EMAIL = r"(?:https?://|www\.)\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
_URL_OR_EMAIL_PATTERN = re.compile(_URL_OR_EMAIL, re.UNICODE)
_CODE_PATTERN = re.compile(r"(?<!\w)[A-Za-z][A-Za-z0-9]*(?:\+\+|#)(?!\w)")
_NUMBER_PATTERN = re.compile(
    r"(?<!\w)(?:\d+(?:[/:.,-]\d+)+%?|\d+%)(?!\w)"
)
_MIXED_CASE_PATTERN = re.compile(
    r"(?<!\w)(?=[A-Za-z0-9]*[a-z])(?=[A-Za-z0-9]+[A-Z])[A-Za-z0-9]+(?!\w)"
)
_ALL_CAPS_PATTERN = re.compile(r"(?<!\w)[A-Z][A-Z0-9]{1,}(?!\w)")
_CJK = r"[぀-ヿ㐀-䶿一-鿿豈-﫿가-힯]+"
TOKEN_PATTERN = re.compile(
    rf"{_URL_OR_EMAIL}|[a-zA-ZÀ-ỹ\d_]+|{_CJK}|\r?\n[\r\n]*|[^\s\w]|[^\s]",
    re.UNICODE,
)
SENTENCE_ENDINGS = {".", "!", "?", "…"}
OPENING_PUNCTUATION = {'"', "'", "“", "‘", "(", "[", "{"}
UNSPACED_BEFORE = set(".,!?;:%)]}")


@dataclass(frozen=True)
class TokenLayout:
    """Original separators surrounding the semantic token sequence."""

    tokens: List[str]
    prefix: str
    separators: List[str]
    suffix: str


def tokenize_for_scan(text: str) -> List[str]:
    return TOKEN_PATTERN.findall(text)


def capture_token_layout(text: str) -> TokenLayout:
    """Capture tokens without losing the whitespace between or around them."""
    matches = list(TOKEN_PATTERN.finditer(text))
    if not matches:
        return TokenLayout(tokens=[], prefix=text, separators=[], suffix="")

    tokens = [match.group(0) for match in matches]
    separators = [
        text[current.end() : following.start()]
        for current, following in zip(matches, matches[1:])
    ]
    return TokenLayout(
        tokens=tokens,
        prefix=text[: matches[0].start()],
        separators=separators,
        suffix=text[matches[-1].end() :],
    )


def protected_literal_spans(text: str) -> List[tuple[int, int]]:
    """Return conservative spans that normalization must not rewrite."""
    candidates: list[tuple[int, int]] = explicit_name_spans(text)
    for pattern in (
        _URL_OR_EMAIL_PATTERN,
        _CODE_PATTERN,
        _NUMBER_PATTERN,
        _MIXED_CASE_PATTERN,
        _ALL_CAPS_PATTERN,
    ):
        for match in pattern.finditer(text):
            start, end = match.span()
            if pattern is _URL_OR_EMAIL_PATTERN:
                while end > start and text[end - 1] in ".,!?;:)]}":
                    end -= 1
            if end > start:
                candidates.append((start, end))

    protected: list[tuple[int, int]] = []
    for start, end in sorted(candidates):
        if protected and start < protected[-1][1]:
            continue
        protected.append((start, end))
    return protected


def explicit_name_spans(text: str) -> List[tuple[int, int]]:
    """Preserve consecutive title-case words; do not infer names from bare text."""
    result: list[tuple[int, int]] = []
    run: list[re.Match[str]] = []
    for word in re.finditer(r"[^\W\d_]+", text):
        gap = text[run[-1].end():word.start()] if run else ""
        contiguous = not run or (gap.isspace() and "\n" not in gap and "\r" not in gap)
        if not word[0].istitle() or not contiguous:
            if len(run) >= 2:
                result.append((run[0].start(), run[-1].end()))
            run = []
        if word[0].istitle():
            run.append(word)
    if len(run) >= 2:
        result.append((run[0].start(), run[-1].end()))
    return result


def is_protected_literal(token: str) -> bool:
    """Whether a token is a URL, code/number literal, or explicit casing signal."""
    if not token:
        return False
    stripped = token.strip(".,!?;:\"'()[]{}…")
    if not stripped:
        return False
    return protected_literal_spans(stripped) == [(0, len(stripped))]


def needs_separator_space(previous: str, token: str) -> bool:
    """Whether a space belongs between ``previous`` and ``token`` when re-joining.

    Words and numbers are space-separated, but never right after an explicit
    line-break token — that would turn "line1\\nline2" into "line1\\n line2".
    """
    if not previous or not token:
        return False
    if not token[0].isalnum():
        return False
    return not previous[-1].isspace()


def preserve_separator(separator: str, token: str) -> str:
    """Keep meaningful layout, but retain the existing punctuation contract."""
    if token and (token[0] in UNSPACED_BEFORE or token[0] in "\r\n"):
        return ""
    return separator


def join_scan_tokens(
    tokens: Iterable[str],
    *,
    separators: List[str] | None = None,
    prefix: str = "",
    suffix: str = "",
) -> str:
    token_list = list(tokens)
    if separators is not None:
        parts = [prefix]
        previous_index: int | None = None
        for index, token in enumerate(token_list):
            if not token:
                continue
            if previous_index is not None:
                separator_index = index - 1
                if separator_index < len(separators):
                    parts.append(preserve_separator(separators[separator_index], token))
            parts.append(token)
            previous_index = index
        parts.append(suffix)
        return "".join(parts)

    parts = []
    for token in token_list:
        if parts and needs_separator_space(parts[-1], token):
            parts.append(" ")
        parts.append(token)
    return "".join(parts)


def extract_word_tokens(tokens: Iterable[str]) -> List[str]:
    return [token for token in tokens if WORD_PATTERN.fullmatch(token)]


def build_cache_key(text: str) -> str:
    normalized = " ".join(text.strip().split()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def capitalize_sentence_starts(text: str) -> str:
    chars = list(text)
    should_capitalize = True
    protected_spans = protected_literal_spans(text)
    protected_index = 0

    for index, char in enumerate(chars):
        while protected_index < len(protected_spans) and index >= protected_spans[protected_index][1]:
            protected_index += 1
        if (
            protected_index < len(protected_spans)
            and protected_spans[protected_index][0] <= index < protected_spans[protected_index][1]
        ):
            if index == protected_spans[protected_index][0]:
                should_capitalize = False
            continue

        if char.isspace():
            continue

        if should_capitalize:
            if char in OPENING_PUNCTUATION:
                continue
            if char.isalpha():
                chars[index] = char.upper()
                should_capitalize = False
                continue
            if char.isdigit():
                should_capitalize = False
                continue

        if char in SENTENCE_ENDINGS:
            should_capitalize = True

    return "".join(chars)
