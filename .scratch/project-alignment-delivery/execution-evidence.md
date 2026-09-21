# Execution evidence: 12 → 14 → 15 → 16

> Mục tiêu hiện hành cập nhật 2026-09-07: [chủ động giải nghĩa teencode, thay đổi so với ban đầu và checklist review tổng thể](teencode-policy-change.md). Chính sách này thay phần “confidence thấp thì giữ nguyên” đối với đề xuất teencode hợp lệ. Các kết quả nghiệm thu cũ chỉ chứng minh phạm vi đã ghi, không tự đóng các kiểm tra mới.

Owner authorization: current execution request and confirmation that runtime is
on this machine; portability to another machine should require minimal changes.
No Kimi Python/key supplied or requested for integration yet. No real inference.

## Completed implementation

- 12: SQLite admission shared by processes on one host; limits per account and
  authenticated user, bounded completion deadline/retries, account/user hashes
  only on disk, per-user cache and in-flight reuse. Failed ledger access denies
  AI. Authenticated API test proves one user's cap does not consume another's
  configured allowance. Separate Python processes prove a shared limit.
- 14: candidate-based AI routing includes short/incomplete text and a single
  diacritic change. Suspected unknown abbreviations remain original and become
  candidates. Dataset-only stays effective. Protected literal/layout changes,
  empty rewrites and invalid confidence are rejected. Fake responses cannot
  alter application consent or budget policy.
- 15: dataset first, AI after idle/boundary, current-input identity on snapshots,
  cancellation on edit, and no stale output eligible for copy/history. Dataset
  and incomplete AI history are marked web_live_partial. Stream interruption
  retains the last partial output.
- 16: bounded previous/definition context participates in cache keys; chunk
  boundaries preserve paragraphs and whole literals. NDJSON sends complete
  snapshots after each candidate chunk. Final completion is explicit. A 5,000
  word / 25 paragraph fake-provider test preserves all words and newlines when
  quota stops AI after one call.

## Validation

- Full backend suite before the last additional regression cases: 439 passed,
  1 skipped, 39 subtests. Follow-up focused suites cover the added authenticated
  API and separate-process cases.
- Frontend unit suite: 31 passed before the stream-interruption regression.
- Frontend production build passed, with default same-origin API.
- Ruff app/tests passed; Mypy passed for the configured 12-file scope. Removed
  one pre-existing duplicate local type annotation in text_utils to restore
  that gate without changing behavior.
- Playwright against real routes/auth with fake AI and in-memory repositories:
  desktop 1440x960 and mobile 390x844 cover dataset, chunk progress, clipboard
  newlines and current-input identity. Added a history-on-navigation scenario.
- Screenshots inspected; fixed the primary output's missing pre-wrap style and
  separated long AI status text from the output heading.

Final rerun: backend **441 passed, 1 skipped, 39 subtests**; frontend **32 passed**;
Playwright **4 passed** (both flows on both viewports); production build, Ruff
and configured Mypy scope passed. Tests use fake AI, not NVIDIA. The remaining
warnings are existing FastAPI/httpx and slowapi deprecations.

The isolated demo is available at http://localhost:5186, backed by localhost:8016.
Its in-memory demo login is `admin_main` / `Admin@123`; these credentials are
fixture data only. Start commands are in backend/tests/serve_progressive_fixture.py
and frontend/tests/progressive.config.ts. The fixture exposes /__test/session
solely on its local test server and is never registered by the application.

## Operational boundary

See [AI runtime and moving machines](../../docs/ai-runtime.md).
The ledger is host-local, not a distributed account quota. All workers sharing
an account must use the same ledger path/settings. Do not run old and new hosts
simultaneously against separate ledgers and claim a shared limit. No external
service, migration, seed or production deployment was introduced.

Wayfinding 04 remains open for full schema/backup/cleanup evidence; its topology
question for 12 is answered. Wayfinding 09 does not authorize deletion of
unknown same-host consumers. Wayfinding 08 and ticket 13 remain open: the owner's
Free Endpoint disclosure describes data restrictions/logging but does not settle
real-work output rights. The owner must provide the Python sample and key only
when Kimi integration is ready to start. Fake tests do not establish Kimi quality,
real provider quota or latency.
