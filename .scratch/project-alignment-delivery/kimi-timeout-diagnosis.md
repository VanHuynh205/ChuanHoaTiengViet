# Kimi timeout diagnosis — 2026-09-07 (UTC+7)

## Conclusion

Latest owner update: the Build UI is now responding and the key has been
replaced. See [new-key check](kimi-new-key-check.md) for current evidence.
The observations below are the earlier diagnostic run, not a claim about the
current state of the Build UI.

The hosted Kimi invocation fails upstream. This is not established as an SSE
parser defect or a Python-client-specific problem: no response headers arrive
for the valid invocation before local deadlines, while invalid input/auth and
model metadata return promptly. NVIDIA's own Build UI also waits/errors,
according to the owner. Exact provider-side cause (capacity, model deployment,
account-specific routing, etc.) remains unknown; do not claim a particular one.

## Reproduction and minimization

Original command: `.venv/Scripts/python.exe backend/tests/smoke_kimi_internal.py`.
It returns failure when the real authenticated normalization API yields zero
verified chunks. The latest run uses reasoning=low from .env and still timed
out after 60 seconds, preserving `Hôm nay dk học phần` with reason `timeout`.

Minimized diagnostic: `.venv/Scripts/python.exe .scratch/project-fit-wayfinding/assets/diagnose_kimi.py --deadline 20`.
Synthetic prompt: `Return only this JSON: {"ok":true}`. No image, database,
normalization pipeline or browser involved. TCP/TLS and sending the body take
about 0.55 seconds; the wait then stalls at receive_response_headers until the
deadline. No credential or reasoning content is in the diagnostic output.

## Falsified and remaining hypotheses

| Probe | Observation |
| --- | --- |
| httpx HTTP/1.1, low, 20s | Timeout waiting for response headers |
| requests, identical payload, 20s | Also timed out; switching libraries is not a fix |
| httpx, same minimal payload, 180s | Still no response headers |
| HTTP/2, low, 30s | Negotiated HTTP/2 successfully, then same header wait |
| Nonstreaming JSON mode | Did not recover the invocation |
| GET /v1/models with current credential | HTTP 200 in 0.65s; Kimi K3 listed among 81 models; not proof of inference permission |
| Intentionally invalid credential | HTTP 401 in 0.7s |
| Empty body with current credential | HTTP 400 in 0.7s; cannot execute inference |
| NVCF-POLL-SECONDS: 5, streaming | HTTP 504 in about 7.7s |
| Same poll header, JSON/nonstreaming | HTTP 504, NVCF-STATUS=errored, empty body, about 7.7s |
| GET documented /v1/status/{requestId} for that failed request | HTTP 404; no recoverable pending result observed |
| NVIDIA Build UI, owner observation | Also waits/errors |

Concrete provider request ID: `b10e026a-ded4-4911-b992-80a52c2a8176`.
Endpoint: `https://integrate.api.nvidia.com/v1/chat/completions`.
Model: `moonshotai/kimi-k3`.
Use these details for a provider support report; do not attach .env or API keys.

## Verified contract

Downloaded and inspected the current official OpenAPI schema from the
[Kimi inference reference](https://docs.api.nvidia.com/nim/reference/moonshotai-kimi-k3-infer).
It permits seed, stream, text messages, max_tokens and reasoning_effort
low/high/max. The request used by the adapter matches those fields.
The [polling reference](https://docs.api.nvidia.com/nim/reference/moonshotai-kimi-k3-statuspolling)
describes 202 and NVCF-REQID; no 202 was observed here.
[Cloud Functions Call Function](https://docs.api.nvidia.com/cloud-functions/reference/invokefunction)
documents NVCF-POLL-SECONDS. Testing it established the upstream 504; it did not
recover the result. Therefore the header and speculative polling were not
added to application requests as a supposed cure.

The [generic invocation guide](https://docs.nvidia.com/nvcf/generic-http-function-invocation)
discusses HTTP/2 keepalive for long-running invocations. Our HTTP/2 probe did not
establish a cure; no custom ping transport or HTTP/2 production dependency was
introduced. h2 was installed locally only for this diagnostic option.

## Application fixes

Final validation: **452 passed, 1 skipped, 39 subtests**; Ruff and configured
Mypy scope passed. No real Kimi smoke passed in this investigation.

- NVIDIA_REASONING_EFFORT=low in .env, Settings and the Kimi adapter default.
- Smoke script honors the configured effort unless explicitly overridden.
- An observed 504 is now AITimeoutError, not a retryable generic network error.
  The regression test first failed against the old behavior, then passed after
  the fix: even with two configured retries, the request is sent once.
- Existing dataset fallback, deadline, admission and truthful timeout state
  remain active. AI_DISABLE_NETWORK remains 1 for normal usage.

The original real smoke remains red due to the provider invocation failure.
Ticket 13 must not be closed as successfully integrated until a real short
normalization completes. No request to another model/provider was substituted.

Diagnostic instrumentation is confined to the explicitly named diagnostic
harness under .scratch; it was not inserted into production code. Public HTML
snapshots and the schema inspector in the same assets directory are diagnostic
evidence, not runtime dependencies. Do not repeatedly run the real probe as an
automated test: canceled requests can still consume provider resources.
