# AI runtime on one machine

Current scope: one host, with a configurable number of local workers. The AI
admission ledger uses Python's standard SQLite library; no Redis service is
required. This is an application budget, not a measurement of NVIDIA quota.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| AI_BUDGET_PATH | .runtime/ai-budget.sqlite3 | Relative to project root, shared by every worker |
| AI_BUDGET_WINDOW_SECONDS | 60 | Sliding attempt window |
| AI_REQUESTS_PER_WINDOW | 30 | Maximum attempts per provider account in the window |
| AI_USER_REQUESTS_PER_WINDOW | 10 | Maximum attempts per authenticated user |
| AI_MAX_CONCURRENCY | 4 | Active provider attempts across workers |
| AI_USER_MAX_CONCURRENCY | 2 | Active attempts per user |
| AI_TIMEOUT_SECONDS | 90 | Overall deadline for one completion, including retries |
| AI_MAX_RETRIES | 2 | Additional attempts; each consumes budget; maximum 5 |
| SEMANTIC_VERIFY_MAX_CHUNKS | 64 | Maximum candidate chunks considered per document |
| SEMANTIC_VERIFY_MAX_TOKENS | 200 | Existing setting: target words per chunk, despite its name |

Keep user limits below global limits to leave capacity for other users. Limits
do not promise fair queuing or reserved capacity under arbitrary aggregate load.
Account and user identifiers are hashed in the ledger. It stores attempt times
and short leases, never prompts, outputs, API keys or tokens. Completed attempts
remain until the window expires; process restart does not reset the limit.
Leases expire after a worker crash. Failure to open/lock the ledger denies AI and
keeps dataset output. Do not delete an active ledger to bypass budget.

All application factory clients use admission; duplicate simultaneous requests
are coalesced within a worker and user. Semantic/disambiguation response caches
are scoped to the authenticated user. Independent workers may repeat an identical
request, but every attempt still consumes the shared budget. Internal CLI callers
share a separate identity. Code that directly instantiates a raw provider client
is a low-level transport API and must not be added as a production bypass.

## Moving to another machine

1. Recreate the Python virtual environment with Python 3.14 (tooling targets
   py311 syntax; 3.14 is the runtime the project is tested on) and install
   backend/requirements.lock (pinned) or backend/requirements.txt. Run npm ci
   inside frontend; do not copy .venv or node_modules from the old machine.
2. Configure SQL_HOST, SQL_INSTANCE, SQL_AUTH and the installed SQL_DRIVER for
   the destination. Dataset files move with the project; SQL data requires a
   separate verified backup/restore. This change does not migrate SQL data.
3. Provide destination secrets privately through environment/local .env. Set
   WEB_ORIGIN for the destination frontend and VITE_API_BASE_URL for development;
   a production frontend defaults to same-origin.
4. Ensure the service account can write AI_BUDGET_PATH. Relative paths are based
   on the project root, independent of the shell working directory. Every local
   worker using the same provider account must use the same absolute ledger path
   and limit settings. Keep the ledger on a local disk, not a network share.
5. Stop using the old host before a single-host cutover. Two simultaneously
   active hosts with separate ledgers do not share account budget. That topology
   needs a shared admission service/database before use; copying this project
   does not establish a distributed quota.
6. Run backend tests and frontend test/build, then test dataset-only and fake AI
   before enabling a real provider. Existing auth/session/SQL setup guidance is
   in SYSTEM_CONTEXT.md and README_setup_sqlserver.md.

## Progressive responses

Existing JSON clients remain compatible. The workspace gets dataset output
first and submits AI after a 700 ms idle interval or a sentence boundary. This
is a debounce choice, not a latency SLA. Requests with progressive=true may
receive application/x-ndjson events containing result and complete. Consumers
must require a complete=true event before calling the stream finished.

Each chunk includes bounded original-text context: up to 60 preceding words
and up to two 80-word earlier definition snippets. Context participates in the
cache key. A changed definition invalidates the affected cache entry. The system
does not recursively feed speculative AI rewrites into later prompts. Budget,
timeout or chunk limits preserve the unprocessed text and report partial scope.

## NVIDIA model boundary

NVIDIA streaming models default to NVIDIA_REASONING_EFFORT=low. The internal smoke honors this
setting unless --reasoning overrides it. NVIDIA_REASONING_TOKEN_RESERVE=2048
allows space for reasoning inside the existing AI_MAX_OUTPUT_TOKENS ceiling;
it is not an observed provider usage amount. Upstream HTTP 504 does not trigger
automatic inference resubmission. Current diagnostic evidence is recorded in
the configured NVIDIA model and records provider diagnostics without credentials.

Text-only requests use a plain message content string. Restart the backend
after changing .env: settings and provider clients are cached for the process.
The smoke script starts a fresh process and reads the current .env each time.

The NVIDIA streaming adapter is implemented for internal tests. Bounded synthetic
smoke attempts are isolated from normal operation. Keep AI_DISABLE_NETWORK=1 for
normal operation. Internal probes use backend/tests/smoke_nvidia_internal.py with no retries and one request
per invocation; do not run it as part of automated test discovery.

The owner reports the Free Endpoint
disclosure forbids confidential/personal data and allows security/improvement
logging. This disclosure alone does not establish permission to use hosted-trial
outputs for real work. Ticket 13 still requires account-contract/trial evidence
before consumer deployment. The owner supplied the sample/key and authorized
synthetic internal tests. Fake AI tests establish
orchestration only, not real model quality, latency or provider quota.
