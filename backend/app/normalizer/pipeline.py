from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.config import Settings
from app.data_manager.pending_service import PendingAbbreviationService
from app.normalizer.abbreviation import expand_abbreviation
from app.normalizer.diacritic_restorer import SyncDiacriticRestorer
from app.normalizer.emoji_remover import remove_emoji_and_emoticons
from app.normalizer.elongation import normalize_elongated_word
from app.normalizer.phrase_index import PhraseIndex, entries_from_phrase_dict
from app.normalizer.phrase_normalizer import PhraseMatch, PhraseNormalizer
from app.normalizer.unicode_normalizer import normalize_unicode
from app.utils.text_utils import capture_token_layout, capitalize_sentence_starts, join_scan_tokens


@dataclass
class NormalizationResult:
    normalized_text: str
    error_types: List[str] = field(default_factory=list)
    pending_submissions: List[Dict[str, object]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    phrase_matches: List[PhraseMatch] = field(default_factory=list)


class VietnameseNormalizerPipeline:
    def __init__(
        self,
        settings: Settings,
        pending_service: PendingAbbreviationService,
        diacritic_restorer: Optional[SyncDiacriticRestorer] = None,
    ) -> None:
        self.settings = settings
        self.pending_service = pending_service
        self._diacritic_restorer = diacritic_restorer
        self.phrase_normalizer = PhraseNormalizer(
            settings=settings, pending_service=pending_service
        )
        self.single_letter_words = set(
            "aàáảãạăằắẳẵặâầấẩẫậ"
            "eèéẻẽẹêềếểễệ"
            "iìíỉĩị"
            "oòóỏõọôồốổỗộơờớởỡợ"
            "uùúủũụưừứửữự"
            "yỳýỷỹỵ"
        )

    def normalize(self, text: str, submitted_by: Optional[str] = None) -> NormalizationResult:
        normalized_text = normalize_unicode(text)
        emoji_result = remove_emoji_and_emoticons(normalized_text, self.settings.data_dir)
        normalized_text = emoji_result.cleaned_text

        diacritic_applied = False
        if self._diacritic_restorer:
            dr = self._diacritic_restorer.restore(normalized_text)
            if dr.applied:
                normalized_text = dr.restored_text
                diacritic_applied = True

        abbreviations = self.pending_service.get_approved_abbreviations()
        abbreviation_keys = abbreviations.keys()
        known_words = self.pending_service.get_dictionary_words()

        phrase_index = self._build_phrase_index()
        phrase_result = self.phrase_normalizer.normalize_phrases(
            normalized_text,
            phrase_index,
            known_words=known_words,
            approved_abbreviations=abbreviations,
            submitted_by=submitted_by,
        )
        tokens = phrase_result.tokens
        layout = capture_token_layout(normalized_text)
        consumed = phrase_result.consumed_token_indices
        replacements = phrase_result.token_replacements

        rebuilt_tokens: List[str] = []
        error_types: List[str] = list(phrase_result.error_types)
        pending_submissions: List[Dict[str, object]] = list(
            phrase_result.pending_phrase_submissions
        )
        warnings: List[str] = []

        if emoji_result.removed_any:
            error_types.append("EMOJI")
        if diacritic_applied:
            error_types.append("DIACRITIC")

        for token_index, token in enumerate(tokens):
            if token_index in consumed:
                rebuilt_tokens.append(replacements.get(token_index, ""))
                continue

            if not token.isalpha():
                rebuilt_tokens.append(token)
                continue

            token_lower = token.lower()
            transformed = normalize_elongated_word(token, known_words, abbreviation_keys)
            transformed_lower = transformed.lower()
            if transformed_lower != token_lower:
                error_types.append("ELONGATION")

            expanded = expand_abbreviation(transformed, abbreviations)
            expanded_lower = expanded.lower()
            if expanded_lower != transformed_lower:
                error_types.append("ABBR")

            should_capture_meaning = self._is_suspected_abbreviation(
                word=transformed,
                expanded=expanded,
                known_words=known_words,
                abbreviations=abbreviations,
            )
            is_known_word = self._is_known_word(transformed, known_words, abbreviations)

            if expanded_lower == transformed_lower and (
                should_capture_meaning or not is_known_word
            ):
                submission = self.pending_service.submit_pending_abbreviation(
                    abbr=transformed,
                    submitted_by=submitted_by,
                    source="cli_runtime",
                )
                submission_payload = dict(submission)
                has_suggested = bool(submission_payload.get("has_suggested", False))
                submission_payload["has_suggested"] = has_suggested
                submission_payload["needs_user_meaning"] = bool(
                    should_capture_meaning
                    and submission_payload.get("pending_id")
                    and not has_suggested
                )
                submission_payload["can_add_more_meanings"] = bool(
                    should_capture_meaning
                    and submission_payload.get("pending_id")
                    and has_suggested
                )
                pending_submissions.append(submission_payload)
                if submission["status"] == "DB_UNAVAILABLE":
                    warnings.append(
                        f"Khong the gui pending cho '{transformed}' vi SQL Server chua san sang."
                    )

            rebuilt_tokens.append(expanded)

        layout_matches_tokens = layout.tokens == tokens
        final_text = capitalize_sentence_starts(
            join_scan_tokens(
                rebuilt_tokens,
                separators=layout.separators if layout_matches_tokens else None,
                prefix=layout.prefix if layout_matches_tokens else "",
                suffix=layout.suffix if layout_matches_tokens else "",
            )
        )
        return NormalizationResult(
            normalized_text=final_text,
            error_types=sorted(set(error_types)),
            pending_submissions=pending_submissions,
            warnings=warnings,
            phrase_matches=list(phrase_result.phrase_matches),
        )

    def _build_phrase_index(self) -> PhraseIndex:
        try:
            data = self.pending_service.get_live_normalization_data()
        except Exception:
            return PhraseIndex.empty(max_ngram=self.settings.phrase_max_ngram)
        overrides = entries_from_phrase_dict(getattr(data, "phrase_overrides", {}) or {})
        db_phrases = entries_from_phrase_dict(getattr(data, "db_phrases", {}) or {})
        mined = entries_from_phrase_dict(getattr(data, "mined_phrases", {}) or {})
        if not (overrides or db_phrases or mined):
            return PhraseIndex.empty(max_ngram=self.settings.phrase_max_ngram)
        return PhraseIndex.build(
            overrides=overrides,
            db_phrases=db_phrases,
            mined=mined,
            max_ngram=self.settings.phrase_max_ngram,
        )

    def _is_known_word(
        self, word: str, known_words: set[str], abbreviations: Dict[str, str]
    ) -> bool:
        lowered = word.lower()
        if len(lowered) == 1 and lowered in self.single_letter_words:
            return True
        if lowered in abbreviations:
            return True
        if self._should_force_suspected_abbreviation(lowered):
            return False
        return lowered in known_words

    def _is_suspected_abbreviation(
        self,
        word: str,
        expanded: str,
        known_words: set[str],
        abbreviations: Dict[str, str],
    ) -> bool:
        lowered = word.lower()
        if expanded.lower() != lowered:
            return False
        if lowered in abbreviations:
            return False
        if len(lowered) == 1:
            return lowered not in self.single_letter_words
        # Unknown words can still be sent to moderation, but only compact
        # vowel-less tokens should ask the user for an original abbreviation meaning.
        return self._should_force_suspected_abbreviation(lowered)

    def _should_force_suspected_abbreviation(self, word: str) -> bool:
        if not (2 <= len(word) <= 3):
            return False
        vowel_count = sum(1 for char in word if _is_vietnamese_vowel(char))
        if vowel_count == 0:
            return True
        core_vowel_count = sum(1 for char in word if _is_core_vietnamese_vowel(char))
        return core_vowel_count == 0 and any(char in "jqxz" for char in word)


def _is_vietnamese_vowel(char: str) -> bool:
    decomposed = unicodedata.normalize("NFD", char.lower())
    return bool(decomposed) and decomposed[0] in "aeiouy"


def _is_core_vietnamese_vowel(char: str) -> bool:
    decomposed = unicodedata.normalize("NFD", char.lower())
    return bool(decomposed) and decomposed[0] in "aeiou"
