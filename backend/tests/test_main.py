import unittest
from unittest.mock import patch

from app.config import DEFAULT_DATA_DIR, Settings
from app.main import capture_pending_meanings, handle_add_meaning_command, run_cli
from app.normalizer.pipeline import VietnameseNormalizerPipeline


class FakePendingService:
    def __init__(self):
        self.captures = []
        self.approvals = []

    def capture_pending_suggestion(self, pending_id, suggested, submitted_by=None):
        status = "SUGGESTION_APPENDED" if suggested == "điều kiện khác" else "SUGGESTION_CAPTURED"
        self.captures.append(
            {
                "pending_id": pending_id,
                "suggested": suggested,
                "submitted_by": submitted_by,
            }
        )
        return {"pending_id": pending_id, "status": status}

    def approve_pending_abbreviation(self, pending_id, reviewer, expanded=None, review_notes=None):
        self.approvals.append(
            {
                "pending_id": pending_id,
                "reviewer": reviewer,
                "expanded": expanded,
                "review_notes": review_notes,
            }
        )
        return {"pending_id": pending_id, "status": "APPROVED"}

    def add_abbreviation_meaning(
        self,
        abbr,
        meaning,
        reviewer,
        domain="general",
        source="admin_manual",
        review_notes=None,
        approve_immediately=False,
    ):
        result = {
            "abbr": abbr.strip().lower(),
            "meaning": meaning,
            "status": "APPROVED" if approve_immediately else "SUGGESTION_CAPTURED",
            "source": source,
            "reviewer": reviewer,
            "review_notes": review_notes,
        }
        self.approvals.append(result)
        return result


class FakeCliPendingService:
    def __init__(self):
        self.added_meanings = []

    def get_approved_abbreviations(self):
        return {"ko": "khong"}

    def get_dictionary_words(self):
        return {"khong", "ngon"}

    def submit_pending_abbreviation(self, **kwargs):
        raise AssertionError("CLI emoji test should not create pending submissions.")

    def add_abbreviation_meaning(
        self,
        abbr,
        meaning,
        reviewer,
        domain="general",
        source="admin_manual",
        review_notes=None,
        approve_immediately=False,
    ):
        result = {
            "abbr": abbr.strip().lower(),
            "meaning": meaning,
            "status": "APPROVED" if approve_immediately else "SUGGESTION_CAPTURED",
        }
        self.added_meanings.append(result)
        return result


class FakeHistoryRepository:
    def log_normalization(self, **kwargs):
        return None


class FakeCliPipeline:
    def __init__(self, settings):
        self.pending_service = FakeCliPendingService()
        self._pipeline = VietnameseNormalizerPipeline(
            settings=settings, pending_service=self.pending_service
        )

    def normalize(self, text, submitted_by=None):
        return self._pipeline.normalize(text, submitted_by)


class CapturePendingMeaningsTests(unittest.TestCase):
    def test_capture_prompts_once_per_abbreviation_and_saves_non_empty_input(self):
        service = FakePendingService()
        prompts = iter(["v\u1eady"])

        capture_pending_meanings(
            pending_service=service,
            pending_submissions=[
                {
                    "abbr": "v",
                    "pending_id": "pending-v",
                    "needs_user_meaning": True,
                    "has_suggested": False,
                },
                {
                    "abbr": "v",
                    "pending_id": "pending-v",
                    "needs_user_meaning": True,
                    "has_suggested": False,
                },
            ],
            submitted_by="cli_user",
            input_func=lambda _prompt: next(prompts),
            output_func=lambda _message: None,
        )

        self.assertEqual(len(service.captures), 1)
        self.assertEqual(service.captures[0]["pending_id"], "pending-v")
        self.assertEqual(service.captures[0]["suggested"], "v\u1eady")

    def test_capture_skips_blank_input(self):
        service = FakePendingService()

        capture_pending_meanings(
            pending_service=service,
            pending_submissions=[
                {
                    "abbr": "\u0111k",
                    "pending_id": "pending-dk",
                    "needs_user_meaning": True,
                    "has_suggested": False,
                },
            ],
            submitted_by="cli_user",
            input_func=lambda _prompt: "   ",
            output_func=lambda _message: None,
        )

        self.assertEqual(service.captures, [])

    def test_capture_ignores_items_that_do_not_need_prompt(self):
        service = FakePendingService()

        capture_pending_meanings(
            pending_service=service,
            pending_submissions=[
                {
                    "abbr": "abcdef",
                    "pending_id": "pending-long",
                    "needs_user_meaning": False,
                    "has_suggested": False,
                },
            ],
            submitted_by="cli_user",
            input_func=lambda _prompt: "ignored",
            output_func=lambda _message: None,
        )

        self.assertEqual(service.captures, [])

    def test_capture_auto_approves_new_meaning_in_admin_mode(self):
        service = FakePendingService()

        capture_pending_meanings(
            pending_service=service,
            pending_submissions=[
                {
                    "abbr": "v",
                    "pending_id": "pending-v",
                    "needs_user_meaning": True,
                    "has_suggested": False,
                },
            ],
            submitted_by="cli_admin",
            input_func=lambda _prompt: "vay",
            output_func=lambda _message: None,
            auto_approve=True,
        )

        self.assertEqual(len(service.captures), 1)
        self.assertEqual(len(service.approvals), 1)
        self.assertEqual(service.approvals[0]["pending_id"], "pending-v")
        self.assertEqual(service.approvals[0]["reviewer"], "cli_admin")

    def test_capture_prompts_for_additional_meaning_when_pending_already_has_suggestion(self):
        service = FakePendingService()

        capture_pending_meanings(
            pending_service=service,
            pending_submissions=[
                {
                    "abbr": "dk",
                    "pending_id": "pending-dk",
                    "needs_user_meaning": False,
                    "has_suggested": True,
                    "can_add_more_meanings": True,
                },
            ],
            submitted_by="cli_user",
            input_func=lambda _prompt: "điều kiện khác",
            output_func=lambda _message: None,
        )

        self.assertEqual(len(service.captures), 1)
        self.assertEqual(service.captures[0]["pending_id"], "pending-dk")
        self.assertEqual(service.captures[0]["suggested"], "điều kiện khác")
        self.assertEqual(service.approvals, [])

    def test_capture_auto_approves_existing_suggested_pending_after_optional_prompt_skip(self):
        service = FakePendingService()

        capture_pending_meanings(
            pending_service=service,
            pending_submissions=[
                {
                    "abbr": "dk",
                    "pending_id": "pending-dk",
                    "needs_user_meaning": False,
                    "has_suggested": True,
                    "can_add_more_meanings": True,
                },
            ],
            submitted_by="cli_admin",
            input_func=lambda _prompt: "   ",
            output_func=lambda _message: None,
            auto_approve=True,
        )

        self.assertEqual(service.captures, [])
        self.assertEqual(len(service.approvals), 1)
        self.assertEqual(service.approvals[0]["pending_id"], "pending-dk")

    def test_capture_auto_approves_after_appending_additional_meaning(self):
        service = FakePendingService()

        capture_pending_meanings(
            pending_service=service,
            pending_submissions=[
                {
                    "abbr": "dk",
                    "pending_id": "pending-dk",
                    "needs_user_meaning": False,
                    "has_suggested": True,
                    "can_add_more_meanings": True,
                },
            ],
            submitted_by="cli_admin",
            input_func=lambda _prompt: "điều kiện khác",
            output_func=lambda _message: None,
            auto_approve=True,
        )

        self.assertEqual(len(service.captures), 1)
        self.assertEqual(service.captures[0]["suggested"], "điều kiện khác")
        self.assertEqual(len(service.approvals), 1)
        self.assertEqual(service.approvals[0]["pending_id"], "pending-dk")


class RunCliTests(unittest.TestCase):
    def test_handle_add_meaning_command_auto_approves_in_admin_mode(self):
        service = FakePendingService()
        outputs = []

        handled = handle_add_meaning_command(
            pending_service=service,
            command_text="/them-nghia dk điều khoản",
            submitted_by="cli_admin",
            input_func=lambda _prompt: (_ for _ in ()).throw(AssertionError("Should not prompt")),
            output_func=outputs.append,
            auto_approve=True,
        )

        self.assertTrue(handled)
        self.assertEqual(service.approvals[0]["abbr"], "dk")
        self.assertEqual(service.approvals[0]["meaning"], "điều khoản")
        self.assertEqual(service.approvals[0]["status"], "APPROVED")
        self.assertIn("Da duyet ngay nghia moi cho 'dk'.", outputs[0])

    def test_handle_add_meaning_command_can_prompt_for_missing_arguments(self):
        service = FakePendingService()
        prompts = iter(["dk", "điều khoản"])

        handled = handle_add_meaning_command(
            pending_service=service,
            command_text="/them-nghia",
            submitted_by="cli_admin",
            input_func=lambda _prompt: next(prompts),
            output_func=lambda _message: None,
            auto_approve=True,
        )

        self.assertTrue(handled)
        self.assertEqual(service.approvals[0]["abbr"], "dk")
        self.assertEqual(service.approvals[0]["meaning"], "điều khoản")

    def test_run_cli_prints_normalized_text_after_removing_emoji(self):
        settings = Settings(data_dir=DEFAULT_DATA_DIR, cli_assume_admin=False)

        with (
            patch("app.main.get_settings", return_value=settings),
            patch("app.main.build_pipeline", return_value=FakeCliPipeline(settings)),
            patch("app.main.HistoryRepository", return_value=FakeHistoryRepository()),
            patch("app.main.capture_pending_meanings", return_value=[]),
            patch("builtins.input", side_effect=["ko\U0001f600ngon", "exit"]),
            patch("builtins.print") as print_mock,
        ):
            run_cli()

        printed_lines = [call.args[0] for call in print_mock.call_args_list if call.args]
        self.assertIn("Dong moi : Khong ngon\n", printed_lines)
        self.assertIn("Loi sua  : ABBR, EMOJI", printed_lines)

    def test_run_cli_handles_add_meaning_command_before_normalize(self):
        settings = Settings(data_dir=DEFAULT_DATA_DIR, cli_assume_admin=True)
        fake_pipeline = FakeCliPipeline(settings)

        with (
            patch("app.main.get_settings", return_value=settings),
            patch("app.main.build_pipeline", return_value=fake_pipeline),
            patch("app.main.HistoryRepository", return_value=FakeHistoryRepository()),
            patch("app.main.capture_pending_meanings", return_value=[]),
            patch("builtins.input", side_effect=["/them-nghia dk điều khoản", "exit"]),
            patch("builtins.print") as print_mock,
        ):
            run_cli()

        printed_lines = [call.args[0] for call in print_mock.call_args_list if call.args]
        self.assertTrue(any("Lenh them nghia nhanh" in line for line in printed_lines))
        self.assertTrue(any("Da duyet ngay nghia moi cho 'dk'." in line for line in printed_lines))


if __name__ == "__main__":
    unittest.main()
