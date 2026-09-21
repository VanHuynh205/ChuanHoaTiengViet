# New key and text-only sample check — 2026-09-07

Owner reports the NVIDIA Build web UI is now responding quickly and supplied
a new text-only requests sample. This supersedes the earlier observation that
the web UI was also slow; it does not itself establish API availability.

## Credential/config checks

- Fresh Python processes read the same NVIDIA_API_KEY value as the root .env.
- No backend/.env exists to override that file.
- The key has the expected nvapi- prefix, no leading/trailing whitespace and
  no extra Bearer prefix. These are format checks, not proof of model permission.
- NVIDIA_REASONING_EFFORT=low. AI_DISABLE_NETWORK=1 remains for normal usage;
  the authorized smoke opts in only in its own process.
- No key, fingerprint, partial key or authorization header was printed.

## Runtime observations

1. Original authenticated API smoke with the new key timed out after 60s and
   preserved dataset output, zero verified chunks.
2. Direct httpx request with content as a string timed out at receive-response-
   headers after 60s; TCP/TLS and sending body completed in about 0.57s.
3. Standalone requests transport with the owner's exact semantic payload:
   model moonshotai/kimi-k3, their Vietnamese capability question as a string,
   max_tokens=16384, seed=0, stream=true, temperature=1, reasoning_effort=low.
   It also failed to receive a response within 60s. It did not use the app's
   smaller token ceiling, system prompt, database or normalization pipeline.
4. Re-ran the original authenticated API smoke after the code edits. It still
   timed out after 60s with semantic_reason=timeout, zero verified chunks and
   preserved dataset text. No successful real inference is claimed.

These results do not identify a client parser cause for the header wait.
Build playground behavior and this machine/account's Free Endpoint behavior
currently differ. Do not carry forward a claim that the Build UI is still down.

## Code findings and edits

- The app previously used a text-content array inherited from the owner's
  earlier vision sample. Both forms are documented, so this was not proven to
  cause the timeout. It is now a plain content string to match the new sample.
- A malformed finish_reason such as a list escaped as TypeError at the set
  membership check. Added a failing transport test, then validated the type
  inside the parser so malformed responses raise AIParseError and use fallback.
- Non-finite numeric usage that raises OverflowError is also classified as an
  AI parsing error instead of escaping the client error contract.

Validation: **453 passed, 1 skipped, 39 subtests**; Ruff and configured Mypy
scope pass. This proves code behavior under tests, not successful real inference.

Ticket 13 remains pending a successful real normalization. Do not enable
consumer traffic or declare the real-model acceptance criteria complete.
