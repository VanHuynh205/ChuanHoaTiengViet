"""NVIDIA Nemotron 3.5 Lightning streaming client."""

from __future__ import annotations

from typing import Any

from app.ai.client import AIRequest
from app.ai.nvidia_streaming_client import NvidiaStreamingClient


class NemotronClient(NvidiaStreamingClient):
    """Reuse the hardened SSE parser while using Nemotron's request contract."""

    def __init__(
        self,
        api_key: str,
        model: str = "nvidia/nemotron-3.5-lightning-30b-a3b",
        reasoning_budget: int = 256,
        **kwargs: Any,
    ) -> None:
        super().__init__(api_key, model=model, reasoning_effort="low", **kwargs)
        self._reasoning_budget = max(0, int(reasoning_budget))

    def _build_body(self, request: AIRequest) -> dict[str, Any]:
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        answer_tokens = min(self._max_output_tokens, max(1, request.max_tokens))
        thinking = request.enable_thinking if request.enable_thinking is not None else True
        reasoning_tokens = (
            min(self._reasoning_budget, self._max_output_tokens - answer_tokens) if thinking else 0
        )
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": request.temperature,
            "top_p": 0.95,
            "max_tokens": answer_tokens + reasoning_tokens,
            "stream": True,
            # extra_body is an OpenAI SDK argument, not a raw HTTP JSON field.
            "chat_template_kwargs": {"enable_thinking": thinking},
            "reasoning_budget": reasoning_tokens,
        }
        if request.json_mode:
            # Without this the fallback leg returns prose, which the JSON
            # verifier then has to reject.
            body["response_format"] = {"type": "json_object"}
        return body
