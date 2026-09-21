# Issue tracker: Local Markdown

Issues and specs live as Markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature>/`.
- Spec: `.scratch/<feature>/spec.md`.
- Implementation tickets: `.scratch/<feature>/issues/<NN>-<slug>.md`,
  numbered from `01`, one file per ticket.
- Record triage state in a `Status:` line near the top of each issue.
  Use the role strings in `triage-labels.md`.
- Append comments and conversation history under `## Comments`.

## Publishing and fetching

When a skill says "publish to the issue tracker", create the appropriate
spec or ticket file using the paths above. Create directories as needed.

When a skill says "fetch the relevant ticket", read the referenced file.
If a number matches multiple features, ask which feature it belongs to.

## Wayfinding operations

Used by `/wayfinder`:

- Map: `.scratch/<effort>/map.md`, containing Notes, Decisions-so-far,
  and Fog.
- Child ticket: `.scratch/<effort>/issues/<NN>-<slug>.md`, numbered
  from `01`, with the question in the body.
- Type: record `research`, `prototype`, `grilling`, or `task` in `Type:`.
- Wayfinding status: use `open`, `claimed`, or `resolved` in `Wayfinding Status:`.
  These are workflow states for wayfinding tickets.
- Blocking: record dependencies in `Blocked by: NN, NN`.
  A ticket is unblocked when all listed tickets have `Wayfinding Status: resolved`.
- Frontier: select the lowest-numbered ticket whose `Wayfinding Status: open`
  and whose blockers are resolved.
- Claim: set `Wayfinding Status: claimed` and save before working.
- Resolve: append the answer under `## Answer`, set `Wayfinding Status: resolved`,
  and add a gist plus link to Decisions-so-far in the map.
