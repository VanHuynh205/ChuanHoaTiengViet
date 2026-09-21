import tempfile
import unittest
from pathlib import Path

from app.config import Settings
from app.data_manager.pending_service import LiveNormalizationData
from app.normalizer.contextual_abbreviation import choose_contextual_option
from app.normalizer.live_normalizer import LiveNormalizerService


class FakePendingService:
    def __init__(self):
        self.submissions = []

    def get_live_normalization_data(self, domain="general", user_id=None):
        records = {
            "ct": {
                "id": "abbr-ct",
                "abbr": "ct",
                "expanded": "c\u00f4ng ty",
                "alternative_expansions": ["chia tay"],
                "domain": domain,
                "source": "test",
            }
        }
        return LiveNormalizationData(
            abbreviations={
                "ct": "c\u00f4ng ty",
                "dk": "\u0111\u00fang kh\u00f4ng",
                "m": "m\u00e0y",
                "ny": "ng\u01b0\u1eddi y\u00eau",
            },
            dictionary_words={
                "m\u00e0y",
                "m\u1edbi",
                "kh\u00f4ng",
                "\u1ed5n",
                "h\u1ea3",
            },
            approved_details=records,
        )

    def submit_pending_abbreviation(self, **kwargs):
        self.submissions.append(kwargs)
        return {"abbr": kwargs["abbr"], "status": "PENDING_CREATED", "pending_id": "pending"}


class ContextualAbbreviationTests(unittest.TestCase):
    def test_choice_prefers_breakup_before_romantic_partner(self):
        choice = choose_contextual_option(
            abbr="ct",
            options=["c\u00f4ng ty", "chia tay"],
            tokens=["m\u00e0y", "m\u1edbi", "ct", "ny", "dk"],
            token_index=2,
            abbreviations={
                "ny": "ng\u01b0\u1eddi y\u00eau",
                "dk": "\u0111\u00fang kh\u00f4ng",
            },
        )

        self.assertIsNotNone(choice)
        self.assertEqual(choice.selected, "chia tay")

    def test_choice_prefers_company_in_work_context(self):
        choice = choose_contextual_option(
            abbr="ct",
            options=["c\u00f4ng ty", "chia tay"],
            tokens=["m\u00ecnh", "l\u00e0m", "ct", "m\u1edbi"],
            token_index=2,
            abbreviations={},
        )

        self.assertIsNotNone(choice)
        self.assertEqual(choice.selected, "c\u00f4ng ty")

    def test_live_normalizer_uses_contextual_choice_as_primary(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        pending_service = FakePendingService()
        service = LiveNormalizerService(settings, pending_service)

        result = service.normalize_live(
            "m\u00e0y m\u1edbi ct ny dk ?",
            submitted_by="demo",
            input_method="typing",
        )

        self.assertEqual(
            result.primary_output,
            "M\u00e0y m\u1edbi chia tay ng\u01b0\u1eddi y\u00eau \u0111\u00fang kh\u00f4ng?",
        )
        self.assertEqual(result.ambiguities[0].selected, "chia tay")
        self.assertEqual(result.variants[0].resolutions[0].meaning, "chia tay")
        self.assertEqual(pending_service.submissions, [])


if __name__ == "__main__":
    unittest.main()
