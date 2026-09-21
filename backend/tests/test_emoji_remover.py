import tempfile
import unittest
from pathlib import Path

from app.config import DEFAULT_DATA_DIR
from app.normalizer.emoji_remover import remove_emoji_and_emoticons


class EmojiRemoverTests(unittest.TestCase):
    def test_removes_unicode_emoji_and_normalizes_spacing(self):
        result = remove_emoji_and_emoticons("xin\U0001f600chao", DEFAULT_DATA_DIR)

        self.assertEqual(result.cleaned_text, "xin chao")
        self.assertTrue(result.removed_any)

    def test_removes_zwj_sequence(self):
        result = remove_emoji_and_emoticons(
            "gia dinh \U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466 vui ve",
            DEFAULT_DATA_DIR,
        )

        self.assertEqual(result.cleaned_text, "gia dinh vui ve")
        self.assertTrue(result.removed_any)

    def test_removes_standalone_emoticon_but_not_embedded_text(self):
        standalone = remove_emoji_and_emoticons("xin :v chao", DEFAULT_DATA_DIR)
        embedded = remove_emoji_and_emoticons("xin:vchao", DEFAULT_DATA_DIR)

        self.assertEqual(standalone.cleaned_text, "xin chao")
        self.assertTrue(standalone.removed_any)
        self.assertEqual(embedded.cleaned_text, "xin:vchao")
        self.assertFalse(embedded.removed_any)

    def test_removes_repeated_parenthesis_emoticon_as_one_unit(self):
        result = remove_emoji_and_emoticons("vui qua :))) hen gap lai", DEFAULT_DATA_DIR)

        self.assertEqual(result.cleaned_text, "vui qua hen gap lai")
        self.assertTrue(result.removed_any)

    def test_removal_keeps_multiple_spaces_and_paragraph_breaks(self):
        result = remove_emoji_and_emoticons(
            "dong  mot😀\n\n\ndong  hai",
            DEFAULT_DATA_DIR,
        )

        self.assertEqual(result.cleaned_text, "dong  mot\n\n\ndong  hai")
        self.assertTrue(result.removed_any)

    def test_returns_original_text_when_emoji_data_is_missing(self):
        data_dir = Path(tempfile.mkdtemp())

        result = remove_emoji_and_emoticons("xin chao", data_dir)

        self.assertEqual(result.cleaned_text, "xin chao")
        self.assertFalse(result.removed_any)


if __name__ == "__main__":
    unittest.main()
