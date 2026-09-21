# Kimi sample supplied by owner — 2026-09-07

Source: Python sample pasted by the project owner from NVIDIA Free Endpoint.
No real API key or response was included. No inference was performed. Current
official-reference lookup failed because the web tool returned HTTP 500.

## Observed request in the sample

- POST https://integrate.api.nvidia.com/v1/chat/completions
- Model: moonshotai/kimi-k3
- Authorization: Bearer $NVIDIA_API_KEY (placeholder)
- stream=true and Accept=text/event-stream
- max_tokens=16384, seed=0, temperature=1, reasoning_effort=max
- User content is an array containing text and an image_url. The example asks
  about an image; the normalization use case should supply text only.
- requests.post(..., stream=True) followed by iter_lines() prints raw SSE lines.
  It does not assemble assistant content, validate structured output, distinguish
  reasoning from final content, or handle finish reason, truncation or pending.

The pasted Markdown escapes and link wrappers must be removed if transcribed.
Python does not expand $NVIDIA_API_KEY inside a normal string: use a server-side
environment lookup. Do not retain a literal placeholder as a credential.

## Comparison with the application

The existing NVIDIA transport in backend/app/ai/client.py is GLM-oriented. It
sets stream=false, sends top_p and chat_template_kwargs and optionally sends
response_format. Those fields are absent from the owner's Kimi sample. It
expects a single JSON response and ignores finish_reason. Reusing these settings
unchanged is not a verified Kimi integration.

The future adapter must preserve the application's asynchronous transport,
shared admission/deadline, authenticated-user cache scope and dataset fallback.
Do not transplant synchronous requests.post into an async route. Provider SSE
is distinct from the application's NDJSON progress snapshots. The sample's
16384 token setting and maximum reasoning are example values, not verified
quota or a reason to bypass the application's configured output budget.

## Remaining evidence

- Account credential/access and observed response lifecycle, including final
  content and finish reason; no actual response was supplied.
- Actual quota/credit: unknown; sample max_tokens is not account quota.
- Hosted-service permission for consumer real-work outputs. The owner clarified
  that outputs are used by users and the project does not intend to collect
  normalization data for unrelated personal purposes. This clarifies purpose;
  it does not supply additional NVIDIA service terms or permission.
- The supplied disclosure addresses confidential/personal data and NVIDIA
  logging/improvement, not the unresolved real-work-use condition in the saved
  trial research. Do not conclude either account-specific permission or an
  account-specific denial without the applicable terms.

No implementation, provider switch, credential change or smoke call was made
in this step. Ticket 13 remains pending its recorded investigation dependencies.
