from app.ai.client import AIRequest
from app.ai.nemotron_client import NemotronClient


def test_raw_http_contract_preserves_policy_and_bounds_reasoning():
    client = NemotronClient("fake", reasoning_budget=2048, max_output_tokens=3000)
    body = client._build_body(AIRequest("text", system="policy", max_tokens=256))
    assert "extra_body" not in body
    assert body["messages"][0] == {"role": "system", "content": "policy"}
    assert body["messages"][1] == {"role": "user", "content": "text"}
    assert body["chat_template_kwargs"] == {"enable_thinking": True}
    assert body["max_tokens"] == 2304
    assert body["reasoning_budget"] == 2048
    assert client._build_body(AIRequest("text", max_tokens=8000))["max_tokens"] == 3000
