# NVIDIA Kimi K3: contract and remaining account evidence

Investigated: 2026-09-06. Research only: no inference, account/key access, installation, or implementation/configuration changes.

## Answer

The model identity is confirmed: `moonshotai/kimi-k3`. The previous review was correct to retain uncertainty about actual quota, latency and Vietnamese quality. Changing only the model name is not a verified integration. A newly established product boundary is that the linked hosted trial terms restrict use to internal testing/evaluation; a small authenticated user group is not by itself proof of that purpose.

## Official contract

- NVIDIA documents POST `https://integrate.api.nvidia.com/v1/chat/completions`, Bearer credentials, system/user messages, `max_tokens` 1–65536, temperature 0–1 (recommended 1), and optional streaming. `top_p` is fixed and not exposed. `reasoning_effort` accepts `low`, `high`, `max`, defaulting to `max`. The reference lists 200, 202, 422, 500. It does not list GLM `chat_template_kwargs` or `response_format`; absence establishes undocumented compatibility, not proven rejection. [K3 inference reference](https://docs.api.nvidia.com/nim/reference/moonshotai-kimi-k3-infer)
- A pending 202 has a documented GET `/v1/status/{requestId}` polling route. Whether the user's synchronous requests encounter it requires observation. [K3 polling](https://docs.api.nvidia.com/nim/reference/moonshotai-kimi-k3-statuspolling)
- The model card states thinking is always enabled and describes structured output, but does not settle the precise hosted JSON-mode request contract. Multi-turn/tool use requires preserved assistant reasoning and tool-call fields; this is not needed merely because independent single-turn normalization requests exist. The card lists a large context window, not a Vietnamese normalization benchmark or latency guarantee. [NVIDIA model card](https://build.nvidia.com/moonshotai/kimi-k3/modelcard)

## Comparison with repository

Read-only evidence: [client](../../../backend/app/ai/client.py:249), [configuration defaults](../../../backend/app/config.py:171).

| Existing behavior | Finding |
|---|---|
| Chat endpoint, Bearer auth, system/user messages | Matching basic documented transport. |
| Default model `z-ai/glm-5.1` | Existing defaults do not target K3; local secret configuration was not inspected. |
| Always sends `top_p: 1` | Outside exposed K3 request contract. Must not assume accepted or effective. |
| Sends `enable_thinking`/`clear_thinking` inside `chat_template_kwargs` | GLM-oriented controls; no established mapping to K3 reasoning effort. |
| No `reasoning_effort` | Cannot claim current request selects low-latency reasoning. |
| JSON mode sends `response_format: {type: json_object}` | Hosted compatibility remains unverified; model capability and API parameter support are different claims. |
| Parses `choices[0].message.content`; ignores finish reason | No handling of documented pending-response lifecycle; cannot distinguish truncated output through finish reason. |
| Default timeout 10 seconds | Product latency suitability unknown, not evidence K3 fails within 10 seconds. |
| Handles 429 cooldown and selected 5xx retries | Useful fallback transport; not evidence of quota allowance. |

## Quota and service scope

The official FAQ says limits vary by model and concurrent demand; account UI is the place to check them. High load can produce extended waits. Therefore no numeric RPM/TPM, unlimited access, or advantage over Gemini can be inferred for this account. [NVIDIA FAQ](https://forums.developer.nvidia.com/t/nvidia-nim-faq/300317)

The model card links these governing trial terms: §§1.2/1.4 limit hosted access and generated content to internal testing/evaluation absent a separate subscription; §§2.6/4.3 restrict confidential/personal data unless expressly permitted. §3.3 includes content among data used for service/product improvement; §2.3 has exceptions, so it is not a blanket no-retention promise. Public text can still contain personal data. These documented constraints require clarifying the intended pilot; they do not select a replacement provider or budget. [NVIDIA API Trial Terms](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf)

## What is resolved versus still empirical

Resolved: model identity; basic endpoint; reasoning contract; concrete discrepancies with GLM-oriented request; trial-scope constraints; lack of evidence for unlimited/superior quota.

Still unknown: account-specific access/rate limits/credits, actual service response variants and JSON acceptance, p50/p95 latency under representative load, reasoning/output token consumption, accuracy and preservation on the project's Vietnamese examples. Documentation cannot replace authorized measurements. Do not obtain the Python sample or call inference in this phase; the user requested that sample when coding begins.

Product behavior supported by existing decisions: AI failure/limit leaves an explicitly incomplete result; dataset output is provisional; no automatic paid fallback; provider choice remains Kimi K3. New question for the user: is this strictly internal evaluation with test data, or actual end-user work? The latter requires resolving trial-service suitability before deployment decisions.
