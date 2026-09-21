from app.config import DEFAULT_DATA_DIR, Settings
from app.data_manager.pending_service import PendingAbbreviationService
from app.normalizer.diacritic_restorer import SyncDiacriticRestorer
from app.normalizer.pipeline import VietnameseNormalizerPipeline


class FakePendingService(PendingAbbreviationService):
    def __init__(self, settings):
        super().__init__(settings)
        self._approved = {
            "ko": "khong",
            "r": "rồi",
            "đk": "đúng không",
            "đc": "được",
            "v": "vậy",
        }
        self._words = {"khong", "ngon", "v", "nt", "là"}
        self.submissions = []
        self.pending_responses = {}

    def db_is_ready(self):
        return False

    def get_approved_abbreviations(self):
        return self._approved

    def get_dictionary_words(self):
        return self._words

    def submit_pending_abbreviation(self, **kwargs):
        self.submissions.append(kwargs)
        default_response = {
            "abbr": kwargs["abbr"],
            "status": "PENDING_CREATED",
            "pending_id": f"pending-{kwargs['abbr']}",
            "has_suggested": False,
        }
        return self.pending_responses.get(kwargs["abbr"], default_response)


def test_pipeline_expands_abbreviation(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = FakePendingService(settings)
    pipeline = VietnameseNormalizerPipeline(settings=settings, pending_service=service)

    result = pipeline.normalize("ko ngon", submitted_by="tester")

    assert result.normalized_text == "Khong ngon"
    assert "ABBR" in result.error_types


def test_pipeline_submits_unknown_word_to_pending(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = FakePendingService(settings)
    pipeline = VietnameseNormalizerPipeline(settings=settings, pending_service=service)

    result = pipeline.normalize("xyz", submitted_by="tester")

    assert service.submissions[0]["abbr"] == "xyz"
    assert result.pending_submissions[0]["status"] == "PENDING_CREATED"
    assert result.pending_submissions[0]["needs_user_meaning"]
    assert not result.pending_submissions[0]["has_suggested"]


def test_single_letter_consonant_is_still_treated_as_suspicious_abbreviation(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = FakePendingService(settings)
    pipeline = VietnameseNormalizerPipeline(settings=settings, pending_service=service)

    result = pipeline.normalize("x", submitted_by="tester")

    assert service.submissions[0]["abbr"] == "x"
    assert result.pending_submissions[0]["needs_user_meaning"]


def test_existing_pending_with_suggested_meaning_allows_adding_another_meaning(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = FakePendingService(settings)
    service.pending_responses["nt"] = {
        "abbr": "nt",
        "status": "PENDING_EXISTS",
        "pending_id": "pending-nt",
        "has_suggested": True,
    }
    pipeline = VietnameseNormalizerPipeline(settings=settings, pending_service=service)

    result = pipeline.normalize("nt", submitted_by="tester")

    assert result.pending_submissions[0]["status"] == "PENDING_EXISTS"
    assert not result.pending_submissions[0]["needs_user_meaning"]
    assert result.pending_submissions[0]["has_suggested"]
    assert result.pending_submissions[0]["can_add_more_meanings"]


def test_approved_abbreviation_does_not_create_pending(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = FakePendingService(settings)
    pipeline = VietnameseNormalizerPipeline(settings=settings, pending_service=service)

    result = pipeline.normalize("r", submitted_by="tester")

    assert result.normalized_text == "Rồi"
    assert result.pending_submissions == []


def test_long_unknown_word_still_goes_pending_without_prompt(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = FakePendingService(settings)
    pipeline = VietnameseNormalizerPipeline(settings=settings, pending_service=service)

    result = pipeline.normalize("abcdef", submitted_by="tester")

    assert service.submissions[0]["abbr"] == "abcdef"
    assert not result.pending_submissions[0]["needs_user_meaning"]


def test_short_regular_words_do_not_request_user_meaning(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = FakePendingService(settings)
    pipeline = VietnameseNormalizerPipeline(settings=settings, pending_service=service)

    result = pipeline.normalize(
        "form size dep emoji on g\u1eedi x\u00f3a", submitted_by="tester"
    )

    actionable = [
        submission["abbr"]
        for submission in result.pending_submissions
        if submission.get("needs_user_meaning")
    ]
    assert actionable == []


def test_multi_word_abbreviation_expansion_keeps_spaces_between_tokens(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = FakePendingService(settings)
    pipeline = VietnameseNormalizerPipeline(settings=settings, pending_service=service)

    result = pipeline.normalize("v là đc r đk", submitted_by="tester")

    assert result.normalized_text == "Vậy là được rồi đúng không"
    assert result.pending_submissions == []


def test_short_consonant_cluster_in_dictionary_still_goes_to_pending(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = FakePendingService(settings)
    pipeline = VietnameseNormalizerPipeline(settings=settings, pending_service=service)

    result = pipeline.normalize("nt", submitted_by="tester")

    assert service.submissions[0]["abbr"] == "nt"
    assert result.pending_submissions[0]["status"] == "PENDING_CREATED"
    assert result.pending_submissions[0]["needs_user_meaning"]


def test_short_diacritized_dictionary_word_is_not_treated_as_abbreviation(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = FakePendingService(settings)
    service._words.update({"để", "chưa"})
    pipeline = VietnameseNormalizerPipeline(settings=settings, pending_service=service)

    result = pipeline.normalize("để chưa", submitted_by="tester")

    assert result.normalized_text == "Để chưa"
    assert service.submissions == []


def test_pipeline_removes_unicode_emoji_and_marks_error_type(tmp_path):
    settings = Settings(data_dir=DEFAULT_DATA_DIR)
    service = FakePendingService(settings)
    pipeline = VietnameseNormalizerPipeline(settings=settings, pending_service=service)

    result = pipeline.normalize("ko\U0001f600ngon", submitted_by="tester")

    assert result.normalized_text == "Khong ngon"
    assert result.pending_submissions == []
    assert result.error_types == ["ABBR", "EMOJI"]


def test_pipeline_removes_standalone_emoticon_without_creating_false_pending(tmp_path):
    settings = Settings(data_dir=DEFAULT_DATA_DIR)
    service = FakePendingService(settings)
    pipeline = VietnameseNormalizerPipeline(settings=settings, pending_service=service)

    result = pipeline.normalize("ko :v", submitted_by="tester")

    assert result.normalized_text == "Khong"
    assert result.pending_submissions == []
    assert service.submissions == []
    assert result.error_types == ["ABBR", "EMOJI"]


def test_pipeline_removes_multiple_emoticon_shapes_and_trims_output(tmp_path):
    settings = Settings(data_dir=DEFAULT_DATA_DIR)
    service = FakePendingService(settings)
    pipeline = VietnameseNormalizerPipeline(settings=settings, pending_service=service)

    result = pipeline.normalize("^^ <3 T_T", submitted_by="tester")

    assert result.normalized_text == ""
    assert result.pending_submissions == []
    assert result.error_types == ["EMOJI"]


def test_pipeline_preserves_protected_literals(tmp_path):
    settings = Settings(data_dir=tmp_path)
    service = FakePendingService(settings)
    restorer = SyncDiacriticRestorer(
        {
            "nvidia": ["nìvidia"],
            "openai": ["ópenai"],
            "toi": ["tôi"],
        }
    )
    pipeline = VietnameseNormalizerPipeline(
        settings=settings,
        pending_service=service,
        diacritic_restorer=restorer,
    )

    result = pipeline.normalize(
        "https://example.com/path?x=1 C++ C# 9/10 50% NVIDIA OpenAI. toi",
        submitted_by="tester",
    )

    assert result.normalized_text == (
        "https://example.com/path?x=1 C++ C# 9/10 50% NVIDIA OpenAI. Tôi"
    )
