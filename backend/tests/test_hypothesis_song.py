"""Test hypothesis: does diacritic work without capitalization?"""

from pathlib import Path
from app.config import Settings
from app.normalizer.live_normalizer import LiveNormalizerService
from app.normalizer.diacritic_restorer import (
    SyncDiacriticRestorer,
    get_shared_bigram_freq,
    get_shared_context_phrase_overrides,
    get_shared_word_map,
)
from app.data_manager.pending_service import PendingAbbreviationService


def _service(data_dir: Path) -> LiveNormalizerService:
    settings = Settings(data_dir=data_dir, diacritic_auto_detect=True)
    restorer = SyncDiacriticRestorer(
        word_map=get_shared_word_map(data_dir),
        detection_threshold=settings.diacritic_detection_threshold,
        min_text_length=settings.diacritic_min_text_length,
        bigram_freq=get_shared_bigram_freq(data_dir),
        context_phrases=get_shared_context_phrase_overrides(data_dir),
    )
    return LiveNormalizerService(
        settings,
        PendingAbbreviationService(settings),
        diacritic_restorer=restorer,
    )


def test_h1_song_works_without_capitalize():
    """H1: If we disable capitalize, 'song' should become 'sống'"""

    input_text = "song tử tế nghe có vẻ là chuyện lớn"

    data_dir = Path(__file__).parents[1] / "data"
    service = _service(data_dir)

    # Use the current uncached segment seam to isolate diacritic restoration
    # from sentence-case formatting.
    result = service._normalize_live_uncached(
        input_text,
        domain="general",
        capitalize=False  # KEY: disable capitalization
    )

    print(f"\n[H1-TEST] Input: {input_text}")
    print(f"[H1-TEST] Output (no capitalize): {result.primary_output}")
    print(f"[H1-TEST] Should start with 'sống': {result.primary_output.startswith('sống')}")

    assert result.primary_output.startswith("sống"), f"Expected 'sống' but got '{result.primary_output[:20]}'"


def test_h3_song_in_middle_of_sentence():
    """H3: 'song' in middle of sentence should restore to 'sống'"""

    input_text = "chu de la song tu te"

    data_dir = Path(__file__).parents[1] / "data"
    service = _service(data_dir)

    result = service.normalize_live(input_text)

    print(f"\n[H3-TEST] Input: {input_text}")
    print(f"[H3-TEST] Output: {result.primary_output}")
    print(f"[H3-TEST] Contains 'sống': {'sống' in result.primary_output}")

    assert "sống" in result.primary_output.lower(), f"Expected 'sống' in output but got: {result.primary_output}"


if __name__ == "__main__":
    test_h1_song_works_without_capitalize()
    test_h3_song_in_middle_of_sentence()
