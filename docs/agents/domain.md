# Domain Docs

This project uses single-context domain documentation.

## Before exploring

- Read `SYSTEM_CONTEXT.md` for the existing project overview.
- Read root `CONTEXT.md`, when present, for domain terms and invariants.
- Read relevant ADRs under `docs/adr/`.

If `CONTEXT.md` or ADRs are absent, proceed silently.
The `/domain-modeling` skill creates them when terms or decisions
are resolved.

## Layout

- `SYSTEM_CONTEXT.md`: existing project overview.
- `CONTEXT.md`: single project-wide domain context.
- `docs/adr/`: project-wide architecture decision records.

## Vocabulary

Use the terms defined in `CONTEXT.md` when naming domain concepts
in issues, proposals, hypotheses, and tests.

If a needed concept is missing, reconsider whether it matches the
project's language; record genuine gaps for `/domain-modeling`.

## ADR conflicts

Explicitly identify any proposal that contradicts an existing ADR,
and explain why the decision should be reconsidered.
