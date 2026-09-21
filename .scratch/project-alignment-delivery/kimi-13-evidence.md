# Ticket 13: Kimi K3 internal integration — 2026-09-07

## Scope and implementation

Owner explicitly authorized internal integration/testing with synthetic text,
without consumer real-work output use. NVIDIA key is read from local server
environment and never copied to artifacts. AI_DISABLE_NETWORK remains 1 for
normal application execution; only the smoke script opts in for its process.

KimiClient uses the supplied text-content array, model moonshotai/kimi-k3,
seed=0, stream=true and reasoning_effort. It does not send GLM top_p,
chat_template_kwargs or undocumented response_format. JSON formatting is
requested by the existing normalization prompt and validated after completion.

The adapter assembles SSE content deltas, ignores reasoning, requires a stop
finish reason and nonempty final text, bounds response size, and rejects
truncated/malformed/uncompleted responses. A 202 acknowledgement is explicitly
rejected as pending and retains dataset output; no polling support is claimed.
Auth/quota errors do not expose response bodies. Factory clients still use the
shared admission ledger and overall deadline, with no paid-provider fallback.

NVIDIA_REASONING_TOKEN_RESERVE=2048 is an application allowance added to the
requested answer budget, clamped by AI_MAX_OUTPUT_TOKENS. It is not a provider
quota or a promise that reasoning will fit. The first smoke preceded this
allowance; the second used it. NVIDIA_REASONING_EFFORT remains max in .env,
matching the owner's sample; low was selected only for the second smoke.

## Observations from real endpoint

Synthetic input for both authorized POST attempts: `hôm nay dk học phần`.
Real FastAPI route and JWT authentication; fake in-memory repositories and
usage repository, with no writes to the operational SQL database.

| Attempt | Setting | Cap | Outcome |
| --- | --- | --- | --- |
| Sandbox connectivity attempt | max | 256 completion tokens, no retry | Connection blocked; no successful provider response |
| Authorized external attempt 1 | max | 60s, 256 completion tokens, no retry | Overall timeout; API 200 with preserved dataset text, semantic error, zero verified chunks |
| Authorized external attempt 2 | low | 60s, 2304 completion tokens, no retry | Overall timeout; API 200, reason timeout, preserved dataset text, zero verified chunks |

Unauthenticated HEAD to the same endpoint returned HTTP 405 with Allow: POST
in under one second. This confirms HTTP reachability, not model access, key
validity or inference availability. No completed response, finish reason,
provider token usage, model quality or quota was observed. A zero successful
response counter does not establish zero provider consumption.

No more real calls were made after these two timeout probes. Do not claim a
successful smoke, or switch to another provider/model to hide this result.

## Validation and remaining gate

Fake transport tests cover SSE text/reasoning separation, JSON fragments,
malformed/truncated/unfinished/empty output, 202, 401 and 429, factory wiring,
shared ledger and token ceiling. Existing client/admission/API/verifier tests
remain relevant. Final test counts are recorded in the ticket after execution.

Final validation: **451 passed, 1 skipped, 39 subtests** in the backend suite;
Ruff app/tests passed; Mypy passed for the configured 13-file scope. No frontend
code was changed in this ticket. Existing deprecation warnings remain.

Implementation is present; ticket 13 is NOT accepted as complete because a
real short normalization has not succeeded. Next investigation must establish
endpoint responsiveness/account model access or a justified longer internal
deadline, with an explicit small test budget. Production use remains outside
the authorized scope.
