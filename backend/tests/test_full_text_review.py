"""Whole-text quality regression at the live-service/provider boundary."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai.semantic_verifier import SemanticVerifier
from app.config import Settings
from app.normalizer.live_normalizer import (
    LiveNormalizerService,
    LiveNormalizationResult,
    LiveVariant,
    _word_change_ranges,
)
from app.ai.review_policy import accept_edits
from app.ai.errors import AIParseError, AITimeoutError
from app.ai.client import AIRequest, AIResponse, NvidiaClient
from app.ai.fallback_client import FallbackClient
from app.ai.errors import AIRateLimitError
from app.ai.nemotron_client import NemotronClient
from app.normalizer.diacritic_restorer import _rule_restore
from app.normalizer.punctuation import restore_terminal_punctuation


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source, expected",
    [
        ("Nhớ nhạc nhau lịch hẹn.", "Nhớ nhắc nhau lịch hẹn."),
        ("Tôi cần kiểm chá thông tin trước khi gửi.", "Tôi cần kiểm tra thông tin trước khi gửi."),
        ("Đừng so sách bản thân với người khác.", "Đừng so sánh bản thân với người khác."),
    ],
)
async def test_ai_reviews_full_text_without_dictionary_ambiguities(tmp_path, source, expected):
    client = SimpleNamespace(
        is_available=lambda: True,
        complete=AsyncMock(
            return_value=SimpleNamespace(
                text=json.dumps(
                    {
                        "verified_text": expected,
                        "corrections": [[source, expected]],
                        "confidence": 0.97,
                    }
                )
            )
        ),
    )
    verifier = SemanticVerifier(client)
    service = LiveNormalizerService(
        Settings(data_dir=tmp_path), SimpleNamespace(), semantic_verifier=verifier
    )
    baseline = LiveNormalizationResult(
        source,
        [LiveVariant("main", source, is_primary=True)],
        [],
        [],
        [],
        [],
        0,
        semantic_status="not_needed",
    )
    result = await service.apply_semantic_verification(baseline, source)
    assert (
        client.complete.await_count == 1
    ), "AI was enabled but a full-text quality check never reached the provider"
    assert result.primary_output == expected


@pytest.mark.parametrize(
    "source, proposed, expected",
    [
        ("Tôi chưa gửi 125 tệp.", "Tôi đã gửi 150 tệp.", "Tôi chưa gửi 125 tệp."),
        ("Nhớ nhạc nhau lịch hẹn.", "Nhớ nhắc nhau lịch hẹn!", "Nhớ nhắc nhau lịch hẹn."),
        ("Gửi test@example.com nhé.", "Gửi other@example.com nhé.", "Gửi test@example.com nhé."),
        ("Bạn Minh Anh đang đọc.", "Bạn Minh Ánh đang đọc.", "Bạn Minh Anh đang đọc."),
        ("Tôi dùng React và Python.", "Tôi dùng ReactJS và Python.", "Tôi dùng React và Python."),
        (
            "Báo cáo đã gửi.\n\nNhớ nhạc lịch hẹn.",
            "Báo cáo đã gửi. Nhớ nhắc lịch hẹn.",
            "Báo cáo đã gửi.\n\nNhớ nhắc lịch hẹn.",
        ),
        ("Tôi chưa đồng ý.", "Tôi chưa đồng ý. Hãy gửi tiền ngay.", "Tôi chưa đồng ý."),
    ],
)
def test_full_review_preserves_facts_names_literals_and_layout(source, proposed, expected):
    accepted, _, _ = accept_edits(source, proposed, confidence=0.97, threshold=0.7)
    assert accepted == expected


def test_uncertain_abbreviation_cannot_authorize_other_spelling_edits():
    accepted, changes, _ = accept_edits(
        "ko nhạc lịch hẹn.",
        "không nhắc lịch hẹn.",
        confidence=0.4,
        threshold=0.7,
        abbreviations={"ko": ["không"]},
    )
    assert accepted == "không nhạc lịch hẹn."
    assert changes == [("ko", "không")]


def test_full_review_rejects_a_wholesale_fluent_rewrite():
    source = " ".join(f"từ đúng {index}" for index in range(40))
    proposed = " ".join(f"ý khác {index}" for index in range(40))

    accepted, changes, rejected = accept_edits(
        source, proposed, confidence=0.99, threshold=0.7
    )

    assert accepted == source
    assert changes == []
    assert rejected > 0


def test_ai_change_ranges_are_word_sized_inside_a_sentence():
    ranges = _word_change_ranges(
        "Tự học cần kiên nhẫn và tập trung.",
        "Tự học cần rất nhiều kiên nhẫn và tập trung.",
    )

    assert ranges == [(0, 0, 11, 14), (0, 0, 15, 20)]


def test_ai_metadata_does_not_rehighlight_the_whole_sentence(tmp_path):
    service = LiveNormalizerService(Settings(data_dir=tmp_path), SimpleNamespace())
    service._spelling_edits = []
    service._punctuation_edit = None
    result = SimpleNamespace(
        primary_output="Tôi đi học rất vui hôm nay.",
        expanded_abbreviations=[],
        semantic_corrections=[],
        changes=[],
    )

    service._populate_change_metadata(
        "Tôi đi học hôm nay.",
        result,
        dataset_output="Tôi đi học hôm nay.",
    )

    assert [change["outputText"] for change in result.changes] == ["rất", "vui"]


def test_ai_cannot_degrade_diacritics_from_dataset_output():
    accepted, changes, rejected = accept_edits(
        "Sống tử tế nghe có vẻ.",
        "Song tu te nghe co ve.",
        confidence=0.97,
        threshold=0.7,
    )
    assert accepted == "Sống tử tế nghe có vẻ."
    assert changes == []
    assert rejected > 0


def test_ai_cannot_choose_an_unlisted_diacritic_candidate():
    accepted, changes, rejected = accept_edits(
        "sự kiên nhẫn",
        "sự kiện nhẫn",
        confidence=0.99,
        threshold=0.7,
        diacritic_candidates={"kien": ["kiên", "kien"]},
    )

    assert accepted == "sự kiên nhẫn"
    assert changes == []
    assert rejected > 0


def test_explicit_names_survive_rule_restoration_before_ai():
    source = "gui tai lieu cho Minh Anh va Thu Ha"
    output, _, _, _ = _rule_restore(
        source,
        {
            "gui": ["gửi"],
            "minh": ["mình"],
            "anh": ["ảnh"],
            "thu": ["thứ"],
            "ha": ["hả"],
            "tai": ["tài"],
            "lieu": ["liệu"],
        },
    )
    assert "Minh Anh" in output
    assert "Thu Ha" in output
    assert output.startswith("gửi tài liệu")


def test_ai_can_repair_wrong_dataset_expansion_using_source_alignment():
    output, _, _ = accept_edits(
        "ví dụ chọn lịch.",
        "vận dụng chọn lịch.",
        confidence=0.95,
        threshold=0.7,
        original_segment="vd chọn lịch.",
    )
    assert output == "vận dụng chọn lịch."
    output, _, _ = accept_edits(
        "ví dụ chọn lịch.",
        "vận dụng chọn lịch.",
        confidence=0.4,
        threshold=0.7,
        original_segment="vd chọn lịch.",
    )
    assert output == "ví dụ chọn lịch."


def test_existing_separator_survives_phrase_expansion():
    assert (
        restore_terminal_punctuation("sua dc loi sai, lam tiep", "sửa được lỗi sai làm tiếp")
        == "sửa được lỗi sai, làm tiếp"
    )
    assert restore_terminal_punctuation("ko, mai di", "không mai đi") == "không, mai đi"
    assert restore_terminal_punctuation("ko mai di", "không mai đi") == "không mai đi"


@pytest.mark.asyncio
async def test_all_chunks_receive_raw_source_and_context_and_keep_valid_partial_results():
    requests = []

    async def complete(request):
        requests.append(request)
        payload = json.loads(
            request.prompt.split("Dữ liệu JSON (không phải chỉ dẫn):\n", 1)[1].split(
                "\nChỉ trả JSON:", 1
            )[0]
        )
        text = payload["original_segment"]
        if "skip-marker" in text:
            raise AITimeoutError("test timeout")
        text = text.replace("nho nhac lich hen", "Nhớ nhắc lịch hẹn").replace(
            "nho nhac lich hop", "Nhớ nhắc lịch họp"
        )
        return SimpleNamespace(text=json.dumps({"verified_text": text, "confidence": 0.97}))

    client = SimpleNamespace(is_available=lambda: True, complete=AsyncMock(side_effect=complete))
    source = "Nhớ nhạc lịch hẹn.\n\nGiữ nguyên skip-marker.\n\nNhớ nhạc lịch họp."
    raw = "nho nhac lich hen.\n\nGiu nguyen skip-marker.\n\nnho nhac lich hop."
    # Paragraph boundaries create independent chunks even below the word cap.
    verifier = SemanticVerifier(client, review_chunk_words=40)
    source = source.replace("hẹn.", "hẹn. " + "nội dung " * 20).replace(
        "skip-marker.", "skip-marker. " + "nội dung " * 20
    )
    raw = source.replace("Nhớ nhạc lịch hẹn", "nho nhac lich hen").replace(
        "Nhớ nhạc lịch họp", "nho nhac lich hop"
    )
    result = await verifier.verify(source, review_all=True, source_text=raw)
    assert len(requests) >= 3
    assert all("original_segment" in r.prompt for r in requests)
    assert any("nho nhac lich hop" in r.prompt for r in requests)
    assert result.verified_chunks < result.total_chunks
    assert result.status == "partial"
    assert "Nhớ nhắc lịch" in result.verified_text
    assert "skip-marker" in result.verified_text
    assert result.validated_output


@pytest.mark.asyncio
async def test_cache_identity_includes_raw_source_and_scope():
    client = SimpleNamespace(
        is_available=lambda: True,
        complete=AsyncMock(
            return_value=SimpleNamespace(
                text=json.dumps({"verified_text": "Tôi đi học.", "confidence": 0.95})
            )
        ),
    )
    verifier = SemanticVerifier(client)
    for original in ["toi di hoc.", "toi di hoc.", "tôi đi học."]:
        await verifier.verify("Tôi đi học.", review_all=True, source_text=original)
    assert client.complete.await_count == 2


@pytest.mark.asyncio
async def test_full_review_reports_unchecked_tail_when_budget_is_exhausted():
    client = SimpleNamespace(
        is_available=lambda: True,
        complete=AsyncMock(
            return_value=SimpleNamespace(
                text=json.dumps({"verified_text": "Nhớ nhắc lịch hẹn.", "confidence": 0.95})
            )
        ),
    )
    verifier = SemanticVerifier(client, max_chunks=1, review_chunk_words=40)
    source = "Nhớ nhạc lịch hẹn. " + "nội dung " * 60
    result = await verifier.verify(source, review_all=True, source_text=source)
    assert result.total_chunks > 1
    assert result.verified_chunks == 1
    assert result.skipped_chunks > 0
    assert result.status == "partial"
    assert result.verified_text.endswith("nội dung ")


def test_nemotron_honors_normalization_sampling_temperature():
    client = NemotronClient("test-only-key")
    body = client._build_body(AIRequest(prompt="test", temperature=0.1, max_tokens=1024))
    assert body["temperature"] == 0.1
    direct = client._build_body(AIRequest(prompt="test", max_tokens=1024, enable_thinking=False))
    assert direct["chat_template_kwargs"]["enable_thinking"] is False
    assert direct["reasoning_budget"] == 0
    assert direct["max_tokens"] == 1024


def test_quality_model_uses_its_own_standard_request_contract():
    client = NvidiaClient("test-only-key", model="google/gemma-4-31b-it")
    body = client._build_body(AIRequest("test", json_mode=True))
    assert "chat_template_kwargs" not in body
    assert body["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_fallback_only_on_provider_failure_and_keeps_actual_model():
    primary = SimpleNamespace(
        is_available=lambda: True, complete=AsyncMock(side_effect=AITimeoutError("timeout"))
    )
    secondary = SimpleNamespace(
        is_available=lambda: True,
        complete=AsyncMock(
            return_value=AIResponse(
                '{"verified_text":"đăng ký học phần","corrections":[["dk","đăng ký"]],"confidence":0.95}',
                20,
                1,
                "actual-fallback",
            )
        ),
    )
    verifier = SemanticVerifier(FallbackClient(primary, secondary))
    result = await verifier.verify(
        "dk học phần",
        review_all=True,
        source_text="dk học phần",
        abbreviation_options={"dk": ["dk"]},
    )
    assert result.fallback_used
    assert result.evidence_proposals[0]["model"] == "actual-fallback"
    primary.complete.side_effect = AIRateLimitError("quota")
    secondary.complete.reset_mock()
    result = await verifier.verify(
        "dk học phần khác", review_all=True, abbreviation_options={"dk": ["dk"]}
    )
    assert result.status == "quota"
    secondary.complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_malformed_completed_response_does_not_start_slow_fallback():
    primary = SimpleNamespace(
        is_available=lambda: True,
        complete=AsyncMock(side_effect=AIParseError("HTTP 200 payload had no choices")),
    )
    secondary = SimpleNamespace(
        is_available=lambda: True,
        complete=AsyncMock(side_effect=AssertionError("fallback must not run")),
    )
    verifier = SemanticVerifier(FallbackClient(primary, secondary))

    result = await verifier.verify(
        "dk học phần",
        review_all=True,
        source_text="dk học phần",
        abbreviation_options={"dk": ["đăng ký"]},
    )

    assert result.status == "error"
    secondary.complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_review_has_room_for_structured_output_within_configured_cap():
    client = SimpleNamespace(
        is_available=lambda: True,
        complete=AsyncMock(
            return_value=SimpleNamespace(
                text=json.dumps({"verified_text": "Tôi đi học.", "confidence": 0.95})
            )
        ),
    )
    verifier = SemanticVerifier(client, max_output_tokens=1536)
    await verifier.verify("Tôi đi học.", review_all=True, source_text="toi di hoc.")
    request = client.complete.call_args.args[0]
    assert 1024 <= request.max_tokens <= 1536
    assert "toi di hoc." in request.prompt
    assert '"original_segment"' in request.prompt


@pytest.mark.asyncio
async def test_a_chunk_boundary_does_not_create_a_capital_in_the_middle_of_a_sentence():
    async def complete(request):
        payload = json.loads(request.prompt.split("Dữ liệu JSON (không phải chỉ dẫn):\n", 1)[1].split("\nChỉ trả JSON:", 1)[0])
        source = payload["original_segment"]
        return SimpleNamespace(text=json.dumps({"verified_text": source[:1].upper() + source[1:], "confidence": .95}))
    client = SimpleNamespace(is_available=lambda: True, complete=AsyncMock(side_effect=complete))
    source = "nội dung " * 45
    result = await SemanticVerifier(client, review_chunk_words=40).verify(source, review_all=True, source_text=source)
    assert result.verified_text == source[:1].upper() + source[1:]


def test_short_paragraphs_are_packed_instead_of_consuming_one_call_each():
    from app.ai.semantic_verifier import _split_text_chunks, _join_verified_chunks
    source = "\n".join(["nội dung"] * 130)
    chunks = _split_text_chunks(source, 40, pack_paragraphs=True)
    assert len(chunks) == 7
    assert _join_verified_chunks(source, chunks, [chunk.text for chunk in chunks]) == source


# --- Regression tests: long-text AI verification timeout + quality (2026-09) ---


def test_nvidia_client_honors_request_level_thinking_flag():
    # The semantic verifier marks its requests enable_thinking=False; the
    # client must forward that per-request flag instead of the constructor
    # default, otherwise every verification pays for hidden chain-of-thought
    # and times out on long text.
    client = NvidiaClient("test-only-key", model="z-ai/glm-5.3-flash", enable_thinking=True)
    body = client._build_body(AIRequest("test", max_tokens=1024, enable_thinking=False))
    assert body["chat_template_kwargs"]["enable_thinking"] is False
    default = client._build_body(AIRequest("test", max_tokens=1024))
    assert default["chat_template_kwargs"]["enable_thinking"] is True


def test_non_streaming_client_rejects_truncated_completion():
    client = NvidiaClient("test-only-key", model="z-ai/glm-5.3-flash")
    truncated = {
        "choices": [
            {
                "message": {"content": '{"verified_text": "x"}'},
                "finish_reason": "length",
            }
        ],
        "usage": {"total_tokens": 10},
    }
    with pytest.raises(AIParseError):
        client._parse_response(truncated, latency_ms=1)
    complete = {
        "choices": [
            {
                "message": {"content": '{"verified_text": "x"}'},
                "finish_reason": "stop",
            }
        ],
        "usage": {"total_tokens": 10},
    }
    assert client._parse_response(complete, latency_ms=1).text == '{"verified_text": "x"}'


def test_nemotron_client_sends_json_mode_when_requested():
    client = NemotronClient("test-only-key")
    body = client._build_body(AIRequest("test", json_mode=True, max_tokens=256))
    assert body["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_fallback_reserves_room_without_killing_a_healthy_primary():
    import asyncio

    class _SleepyClient:
        model = "sleepy"

        def __init__(self, delay: float, text: str) -> None:
            self.delay = delay
            self.text = text
            # FallbackClient reads the timeout from the child's _settings.
            self._settings = SimpleNamespace(ai_timeout_seconds=0.9)

        def is_available(self) -> bool:
            return True

        async def complete(self, request):
            await asyncio.sleep(self.delay)
            return AIResponse(self.text, 1, 0, self.model)

    # Primary finishes at ~0.50s. The legacy 30s/2 cap cancelled it at 0.45s
    # and reran the whole request on the fallback; the reservation policy must
    # leave the healthy primary enough room inside the shared 0.9s deadline.
    primary = _SleepyClient(0.5, "healthy")
    fallback = _SleepyClient(0.0, "fallback")
    result = await FallbackClient(primary, fallback).complete(AIRequest("healthy"))
    assert result.text == "healthy"
    assert result.fallback_used is False


def test_uncertain_abbreviation_edit_must_choose_offered_meaning():
    # Below the confidence threshold the AI may only apply meanings the
    # dataset itself offered as options — never an invented substitute.
    accepted, changes, _ = accept_edits(
        "ko nhạc lịch hẹn.",
        "chẳng nhắc lịch hẹn.",
        confidence=0.4,
        threshold=0.7,
        abbreviations={"ko": ["không"]},
    )
    assert accepted == "ko nhạc lịch hẹn."
    assert changes == []


def test_expansion_repairs_are_bounded_by_the_contextual_edit_budget():
    # Repairing a wrong dataset expansion is legitimate, but rewriting every
    # expansion in a chunk is a wholesale rewrite and must hit the budget.
    # Since policy v6 the overflow no longer reverts the whole chunk: the
    # edits that fit the budget (text order) are kept, the rest serve the
    # baseline. 30 sentences x 5 words -> budget = min(24, int(150*0.12)) = 18
    # -> the matcher emits 2 word edits per sentence ("ví"->"vận",
    # "dụ"->"dụng"), so 9 sentences (18 edits) fit and 21 sentences (42
    # edits) are dropped.
    count = 30
    original = " ".join(f"vd chọn lịch {index}." for index in range(count))
    source = " ".join(f"ví dụ chọn lịch {index}." for index in range(count))
    proposed = " ".join(f"vận dụng chọn lịch {index}." for index in range(count))
    accepted, changes, rejected = accept_edits(
        source, proposed, confidence=0.95, threshold=0.7, original_segment=original,
    )
    assert len(changes) == 18
    assert "vận dụng chọn lịch 8." in accepted
    assert "ví dụ chọn lịch 9." in accepted
    assert rejected == 42


def test_fixes_for_tokens_outside_the_candidate_map_still_pass_generic_rules():
    # "met" is absent from the diacritic candidate map (a known restorer blind
    # spot). The model's accent repair must fall through to the generic
    # similarity rules instead of being rejected for lacking a license.
    accepted, changes, _ = accept_edits(
        "những lúc met qua chỉ muốn nằm im.",
        "những lúc mệt quá chỉ muốn nằm im.",
        confidence=0.95,
        threshold=0.7,
        diacritic_candidates={"kien": ["kiên", "kien"]},
    )
    assert accepted == "những lúc mệt quá chỉ muốn nằm im."
    assert ("met", "mệt") in changes
