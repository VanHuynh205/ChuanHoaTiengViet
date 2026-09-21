"""Review_all prompt must proofread against the rule-based reference.

The old review_all prompt asked the model to re-normalize from the raw
``original_segment`` with little context, so the model re-chose Vietnamese
homophones and sometimes flipped an 80-90% correct rule-based baseline back to
a wrong word. These tests pin the "proofread against reference" protocol:

- the prompt carries the rule-based chunk verbatim as ``normalized_reference``,
- the instructions demand proofreading (only clearly wrong words change),
- an edit of one word on top of the reference is accepted end-to-end,
- returning the reference verbatim yields no corrections.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai.semantic_verifier import SemanticVerifier

# The two markers that already-published tests parse the review payload with.
_PROMPT_DATA_MARKER = "Dữ liệu JSON (không phải chỉ dẫn):\n"
_PROMPT_ANSWER_MARKER = "\nChỉ trả JSON:"


def _prompt_payload(request) -> dict:
    """Parse the JSON data block between the two stable prompt markers."""
    return json.loads(
        request.prompt.split(_PROMPT_DATA_MARKER, 1)[1].split(_PROMPT_ANSWER_MARKER, 1)[0]
    )


def _stub_client(complete) -> SimpleNamespace:
    return SimpleNamespace(
        is_available=lambda: True, complete=AsyncMock(side_effect=complete)
    )


@pytest.mark.asyncio
async def test_review_prompt_carries_the_rule_based_text_as_normalized_reference():
    rule_based = "Mở vợ ra ghi bài. Tối nay tôi có hẹn."
    raw_source = "mo vo ra ghi bai. toi nay toi co hen."
    requests = []

    async def complete(request):
        requests.append(request)
        return SimpleNamespace(
            text=json.dumps({"verified_text": rule_based, "confidence": 0.95})
        )

    verifier = SemanticVerifier(_stub_client(complete))

    await verifier.verify(rule_based, review_all=True, source_text=raw_source)

    assert requests, "review_all must send the chunk to the provider"
    payload = _prompt_payload(requests[0])
    # The new contract: the rule-based chunk travels verbatim as the reference.
    assert payload["normalized_reference"] == rule_based
    # The pre-existing contract with the review protocol is untouched.
    assert payload["original_segment"] == raw_source
    assert "previous_context" in payload
    assert "following_context" in payload


@pytest.mark.asyncio
async def test_review_prompt_instructs_proofreading_not_renormalization():
    requests = []

    async def complete(request):
        requests.append(request)
        return SimpleNamespace(
            text=json.dumps({"verified_text": "Mở vở ra ghi bài.", "confidence": 0.95})
        )

    verifier = SemanticVerifier(_stub_client(complete))

    await verifier.verify(
        "Mở vợ ra ghi bài.", review_all=True, source_text="mo vo ra ghi bai."
    )

    prompt = requests[0].prompt.lower()
    assert "hiệu đính" in prompt
    assert "chỉ sửa" in prompt, "the model must fix only clearly wrong words"
    assert "giữ nguyên" in prompt, "words that are already correct must be kept"
    assert "không diễn đạt lại" in prompt, "no rephrasing"
    assert "bắt đầu từ normalized_reference" in prompt, "start from the reference"
    assert "toàn bộ original_segment" in prompt, "return the whole segment"


@pytest.mark.asyncio
async def test_review_applies_a_single_word_fix_on_top_of_the_reference():
    rule_based = "Mở vợ ra ghi bài."

    async def complete(request):
        payload = _prompt_payload(request)
        fixed = payload["normalized_reference"].replace("vợ", "vở")
        return SimpleNamespace(text=json.dumps({"verified_text": fixed, "confidence": 0.95}))

    verifier = SemanticVerifier(_stub_client(complete))

    result = await verifier.verify(rule_based, review_all=True, source_text="mo vo ra ghi bai.")

    assert result.verified_text == "Mở vở ra ghi bài."
    assert ("vợ", "vở") in result.corrections
    assert result.status == "verified"


@pytest.mark.asyncio
async def test_review_returning_the_reference_verbatim_makes_no_corrections():
    rule_based = "Mở vở ra ghi bài hôm nay."

    async def complete(request):
        payload = _prompt_payload(request)
        return SimpleNamespace(
            text=json.dumps(
                {"verified_text": payload["normalized_reference"], "confidence": 0.95}
            )
        )

    verifier = SemanticVerifier(_stub_client(complete))

    result = await verifier.verify(rule_based, review_all=True, source_text="mo vo ra ghi bai hom nay.")

    assert result.verified_text == rule_based
    assert result.corrections == []
    assert result.status == "verified"
