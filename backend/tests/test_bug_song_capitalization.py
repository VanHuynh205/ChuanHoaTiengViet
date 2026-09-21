"""Test case for bug: 'song' incorrectly capitalized as 'Song' instead of 'Sống'"""

from pathlib import Path
from app.config import Settings
from app.normalizer.live_normalizer import LiveNormalizerService
from app.data_manager.pending_service import PendingAbbreviationService
from app.normalizer.diacritic_restorer import (
    SyncDiacriticRestorer,
    get_shared_word_map,
    get_shared_bigram_freq,
    get_shared_context_phrase_overrides,
)


def test_song_should_normalize_to_song_not_song_capitalized():
    """Reproduce bug: 'song' at start of text should become 'Sống' not 'Song'."""

    # Exact input from user report
    input_text = """song tử tế nghe có vẻ là chuyện lớn, nhưng thật ra nó bat dau tu nhung viec nho ma mn co the lam moi ngay, k can tien nhieu, k can dia vi cao, k can phai noi nhung cau thật hay. do co the la giu cua cho nguoi di sau, noi cam on voi chu bao ve, de xe gon hon mot chut, k chen hang, k noi loi lam ng khac kho xu, hoac don rac cua minh sau khi an xong. nhung viec nho nay neu nhin rieng le thi co ve k dang ke, nhưng neu ai cx lam mot chut, khong gian chung se de tho hon rất nhiều 🌿."""

    # Expected: "Sống tử tế nghe..." not "Song tử tế nghe..."
    expected_start = "Sống tử tế"

    data_dir = Path(__file__).parents[1] / "data"
    settings = Settings(data_dir=data_dir, diacritic_auto_detect=True)

    # Properly initialize diacritic restorer
    word_map = get_shared_word_map(data_dir)
    bigram_freq = get_shared_bigram_freq(data_dir)
    context_phrases = get_shared_context_phrase_overrides(data_dir)
    restorer = SyncDiacriticRestorer(
        word_map=word_map,
        detection_threshold=settings.diacritic_detection_threshold,
        min_text_length=settings.diacritic_min_text_length,
        bigram_freq=bigram_freq,
        context_phrases=context_phrases,
    )

    service = LiveNormalizerService(
        settings,
        PendingAbbreviationService(settings),
        diacritic_restorer=restorer,
    )

    result = service.normalize_live(input_text)
    output = result.primary_output

    print(f"\n[DEBUG-song] Input start: {input_text[:50]}")
    print(f"[DEBUG-song] Output start: {output[:50]}")
    print(f"[DEBUG-song] Expected start: {expected_start}")
    print(f"[DEBUG-song] Diacritic applied: {result.diacritic_applied}")
    print(f"[DEBUG-song] Diacritic changes: {result.diacritic_changes[:5]}")

    # Bug assertion: Currently fails because output starts with "Song" not "Sống"
    assert output.startswith(expected_start), f"Expected '{expected_start}' but got '{output[:20]}'"


def test_mixed_text_keeps_valid_unaccented_words_and_short_shorthand():
    """Mixed input must not turn valid words/abbreviations into other words."""

    data_dir = Path(__file__).parents[1] / "data"
    settings = Settings(data_dir=data_dir, diacritic_auto_detect=True)
    restorer = SyncDiacriticRestorer(
        word_map=get_shared_word_map(data_dir),
        detection_threshold=settings.diacritic_detection_threshold,
        min_text_length=settings.diacritic_min_text_length,
        bigram_freq=get_shared_bigram_freq(data_dir),
        context_phrases=get_shared_context_phrase_overrides(data_dir),
    )

    result = restorer.restore("song tử tế nghe có vẻ như vườn hoa, vd đi trong lớp")

    assert result.restored_text.startswith("sống tử tế nghe có vẻ")
    assert "vườn hoa" in result.restored_text
    assert "vd đi trong lớp" in result.restored_text
