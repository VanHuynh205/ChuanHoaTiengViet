"""Context-phrase restoration must not overwrite user-typed diacritics.

Real-world failure: "su kiên nhẫn" (user typed "kiên" correctly) was rewritten
to "sự kiện nhẫn" because the context phrase ("su kien" → "sự kiện") replaced
every position inside its match span, including the already-accented token.
"""

from __future__ import annotations

from app.normalizer.diacritic_restorer import (
    SyncDiacriticRestorer,
    _context_phrase_overrides,
)

PHRASES = {
    ("su", "kien"): ("sự", "kiện"),
    ("san", "sang"): ("sẵn", "sàng"),
}


def _restore(text: str) -> str:
    restorer = SyncDiacriticRestorer(
        word_map={},
        bigram_freq={},
        context_phrases=PHRASES,
        min_text_length=1,
        detection_threshold=0.0,
    )
    return restorer.restore(text).restored_text


def test_context_phrase_keeps_user_typed_accent():
    assert _restore("su kiên nhẫn") == "sự kiên nhẫn"


def test_context_phrase_repairs_bare_token_next_to_accented_one():
    assert _restore("san sàng") == "sẵn sàng"


def test_fully_bare_phrase_still_expands():
    assert _restore("su kien nhan") == "sự kiện nhan"


def test_override_writer_skips_diacritized_positions():
    overrides = _context_phrase_overrides(["su", "kiên"], PHRASES)
    assert overrides == {0: "sự"}


def test_builtin_chat_collocations_repair_bare_pairs():
    from app.normalizer.diacritic_restorer import _BUILTIN_CONTEXT_PHRASE_OVERRIDES

    restorer = SyncDiacriticRestorer(
        word_map={},
        bigram_freq={},
        context_phrases=_BUILTIN_CONTEXT_PHRASE_OVERRIDES,
        min_text_length=1,
        detection_threshold=0.0,
    )
    assert restorer.restore("mo vo ra").restored_text == "mở vở ra"
    assert restorer.restore("qua tai").restored_text == "quá tải"
    assert restorer.restore("co gang").restored_text == "cố gắng"
    assert restorer.restore("nam im").restored_text == "nằm im"
    assert restorer.restore("tien tro").restored_text == "tiền trọ"
