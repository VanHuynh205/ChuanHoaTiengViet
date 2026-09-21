import json
from pathlib import Path
import pytest

from app.config import Settings
from app.data_manager.pending_service import LiveNormalizationData
from app.normalizer.spelling import apply_known_spelling
from app.normalizer.punctuation import append_question_mark, preserves_punctuation
from app.normalizer.live_normalizer import LiveNormalizerService
from app.api.schemas import LiveNormalizeResponse

DATA = Path(__file__).parents[1] / "data"
FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures/spelling_regression.json").read_text(encoding="utf-8")
)


class Dataset:
    def get_live_normalization_data(self, **kwargs):
        details = {
            key: {"expanded": meaning, "alternative_expansions": [], "source": "test"}
            for key, meaning in {"mk": "mình", "ko": "không"}.items()
        }
        return LiveNormalizationData(
            {k: d["expanded"] for k, d in details.items()},
            frozenset(
                "xin đăng ký rồi học phần tại sao chưa bao giờ đi hôm nay không mình".split()
            ),
            details,
        )

    def submit_pending_abbreviation(self, **kwargs):
        return {"abbr": kwargs["abbr"], "status": "SKIPPED"}


@pytest.mark.parametrize("case", FIXTURES, ids=lambda c: c["label"] + ":" + c["input"])
def test_labeled_spelling_regression(case):
    output, changes = apply_known_spelling(case["input"], str(DATA))
    assert output == case["expected"]
    assert len(changes) == case["spelling"]
    for change in changes:
        assert change["kinds"] == ["spelling"]
        assert change["reason"] == "known_typo"
        assert change["confidence"] == 0.99


@pytest.mark.parametrize(
    "source",
    ["đăn ký", "xin đăn ký học phần", "mk đăn ký học phần", "ko đăn ký", "đăn ký rồi đăn ký"],
)
def test_live_spelling_metadata_and_mixed_types(source):
    service = LiveNormalizerService(Settings(data_dir=DATA, diacritic_auto_detect=False), Dataset())
    result = service.normalize_live(source)
    payload = LiveNormalizeResponse.model_validate(result.to_payload()).model_dump(by_alias=True)
    spelling = [change for change in payload["changes"] if change["reason"] == "known_typo"]
    assert len(spelling) == source.count("đăn ký")
    for change in spelling:
        assert change["kinds"] == ["spelling"]
        assert change["confidence"] == 0.99
        assert source[change["originalStart"] : change["originalEnd"]] == "đăn ký"
        assert (
            payload["primaryOutput"][change["outputStart"] : change["outputEnd"]].lower()
            == "đăng ký"
        )
    if source.startswith(("mk", "ko")):
        assert any(c["kinds"] == ["teencode"] for c in payload["changes"])


@pytest.mark.parametrize(
    "source",
    [
        "tại sao chưa đăng ký",
        "Vì sao chưa đi",
        "bao giờ đi",
        "bao nhiêu người",
        "tại sao chưa đi  \n",
    ],
)
def test_punctuation_insertion_is_idempotent_and_has_empty_source_span(source):
    output, change = append_question_mark(source)
    assert output.count("?") == 1
    assert "!" not in output
    assert change["kinds"] == ["punctuation"]
    assert change["originalStart"] == change["originalEnd"]
    assert source[change["originalStart"] : change["originalEnd"]] == ""
    assert output[change["outputStart"] : change["outputEnd"]] == "?"
    assert append_question_mark(output) == (output, None)


@pytest.mark.parametrize(
    "source",
    [
        "ai cũng biết",
        "gì cũng được",
        "hôm nay đi học",
        "tại sao",
        "tại sao chưa đi?",
        "tại sao chưa đi!",
        "tại sao chưa đi.",
        "tại sao chưa đi;",
        "tại sao gửi https://example.com",
        "tại sao số 3.14",
        "tại sao gửi a@b.com",
        "tại sao mã ABC_123",
        "tại sao x = y",
        "tại sao chưa đi…",
    ],
)
def test_punctuation_preserves_uncertain_and_protected_text(source):
    assert append_question_mark(source) == (source, None)


def test_live_punctuation_span_after_teencode_and_typo():
    source = "tại sao ko đăn ký"
    result = LiveNormalizerService(
        Settings(data_dir=DATA, diacritic_auto_detect=False), Dataset()
    ).normalize_live(source)
    assert result.primary_output.endswith("?")
    punctuation = [c for c in result.changes if c["kinds"] == ["punctuation"]]
    assert len(punctuation) == 1
    assert punctuation[0]["originalStart"] == punctuation[0]["originalEnd"] == len(source)
    assert result.primary_output[punctuation[0]["outputStart"] : punctuation[0]["outputEnd"]] == "?"
    assert any(c.get("reason") == "known_typo" for c in result.changes)
    assert any(c["kinds"] == ["teencode"] for c in result.changes)


def test_ai_cannot_bypass_punctuation_policy():
    assert not preserves_punctuation("xin đk", "xin đăng ký!")
    assert not preserves_punctuation("xin đk?", "xin đăng ký")
    assert preserves_punctuation("tại sao ko đi?", "tại sao không đi?")
