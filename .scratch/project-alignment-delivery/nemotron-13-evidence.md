# Ticket 13 — Nemotron verification, 2026-09-07

The owner explicitly replaced Kimi with `nvidia/nemotron-3.5-lightning-30b-a3b`
and requested completion of ticket 13. This supersedes the original model target,
not the internal synthetic-data scope. No production deployment or quota claim.

## Reproduction and correction

Command: `.venv/Scripts/python.exe backend/tests/smoke_kimi_internal.py`.
The smoke now defaults to the configured model (previously it forced Kimi).
It exercises the real authenticated FastAPI normalization route, provider factory,
shared admission budget, SSE parser and semantic verifier, using in-memory data/auth
repositories and temporary storage. Operational SQL data is not modified.

1. Sandbox blocked network; the same command was rerun with network approval.
2. Initial Nemotron request: HTTP 400 in 0.648 seconds, zero verified chunks.
   A minimal synthetic raw HTTP probe returned in 0.538 seconds:
   `Validation: Unsupported parameter(s): extra_body`.
3. Fixed raw HTTP fields: `chat_template_kwargs` and `reasoning_budget` at top
   level. `extra_body` is an SDK argument, not a wire field. Also preserved the
   system instruction and reserved answer tokens separately within the total cap.
4. With the previous 16384 reasoning configuration (clamped to the 8192 total
   cap), headers arrived HTTP 200 in approximately 0.7 seconds but the complete
   response exceeded the 60-second deadline. Dataset fallback remained intact.
5. With reasoning budget 256: completed in 6.213 seconds, one verified chunk,
   status `uncertain/unresolved_meaning`; ambiguous `dk` preserved.
6. Saved budget 256 to local .env and the default. Repeated without overrides:
   **13.119 seconds, HTTP 200, verified/provider_checked, one verified chunk**.
   Input: `hôm nay dk học phần`. Output: **`Hôm nay đăng ký học phần`**.

Thus the old *waiting for headers* symptom was not reproduced with Nemotron.
A separate request-format error and an excessive reasoning allocation were found.
This does not establish that Kimi itself is fixed or prove a cause for its historical
upstream timeout. No Kimi inference was sent during this verification.

## Validation and limits

- Regression test failed before the fix and passes after it; checks raw payload,
  preservation of system instructions and reasoning/answer token ceiling.
- Factory contract covers both Kimi and Nemotron through the shared budget.
- Backend: **455 passed, 1 skipped, 39 subtests**. Ruff passed; Mypy passed (14 files).
- Frontend result-pane and live-normalize hook: **9 passed**, rerun outside
  sandbox after esbuild access denial.
- Two real successful completions demonstrate variability, not broad Vietnamese
  quality or latency guarantees. Usage reported zero tokens locally because this
  stream did not supply usable usage totals; this does not mean zero consumption.
- Key stays server-side; no credentials in artifacts. `AI_DISABLE_NETWORK=1`
  remains set for normal app execution. Smoke enables network only in its process.
- UI verification is through existing automated component/hook tests, not a live
  browser connected to NVIDIA. No production readiness claim.

Reference: [NVIDIA Build model sample](https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b/build).
