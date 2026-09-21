"""Shared helpers for reading DataDauCau diacritic CSV files."""

from __future__ import annotations

import csv
import string
from collections.abc import Iterable, Iterator
from pathlib import Path

STRIP_CHARS = string.punctuation + "\u2026\u201c\u201d\u2018\u2019"
NO_DIACRITICS_COLUMN = "no_diacritics"
WITH_DIACRITICS_COLUMN = "with_diacritics"


def iter_diacritic_pairs(input_paths: Iterable[Path]) -> Iterator[tuple[str, str]]:
    """Yield ``(no_diacritics, with_diacritics)`` rows from one or more CSV files."""
    for input_path in input_paths:
        if not input_path.exists():
            raise FileNotFoundError(input_path)

        with input_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            _validate_columns(input_path, reader.fieldnames)
            for row in reader:
                no_diacritics = (row.get(NO_DIACRITICS_COLUMN) or "").strip()
                with_diacritics = (row.get(WITH_DIACRITICS_COLUMN) or "").strip()
                if no_diacritics and with_diacritics:
                    yield no_diacritics, with_diacritics


def clean_token(token: str) -> str:
    """Return a lower-case alphabetic token without surrounding punctuation."""
    cleaned = token.lower().strip(STRIP_CHARS)
    return cleaned if cleaned.isalpha() else ""


def tokenize_words(text: str) -> list[str]:
    """Tokenize by whitespace, keeping only alphabetic words."""
    return [cleaned for token in text.split() if (cleaned := clean_token(token))]


def build_few_shot_examples(
    input_paths: Iterable[Path],
    count: int,
    max_chars: int = 180,
) -> list[dict[str, str]]:
    """Select deterministic short examples for AI fallback prompts."""
    examples: list[dict[str, str]] = []
    seen: set[str] = set()
    for no_diacritics, with_diacritics in iter_diacritic_pairs(input_paths):
        if len(no_diacritics) > max_chars or len(with_diacritics) > max_chars:
            continue
        if no_diacritics in seen:
            continue
        seen.add(no_diacritics)
        examples.append(
            {
                "no_diacritics": no_diacritics,
                "with_diacritics": with_diacritics,
            }
        )
        if len(examples) >= count:
            break
    return examples


def _validate_columns(input_path: Path, fieldnames: list[str] | None) -> None:
    fields = set(fieldnames or [])
    required = {NO_DIACRITICS_COLUMN, WITH_DIACRITICS_COLUMN}
    if not required.issubset(fields):
        expected = ", ".join(sorted(required))
        actual = ", ".join(fieldnames or [])
        raise ValueError(f"{input_path} must contain columns: {expected}; got: {actual}")
