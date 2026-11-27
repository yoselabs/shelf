---
id: 0018
title: A blueprint checkpoint is enforced from the pin; a waiver is the only way to wait
statement: The pinned blueprint tag decides which checkpoints a repo is judged by, so a new checkpoint fails like any other after a pin bump; a repo waives one in its own config with a reason and an expiry date, and an expired waiver fails.
concerns: [gate]
status: accepted
decided_by: owner
updated: 2026-11-28
distilled_into: N/A — self-enforcing via the blueprint audit's waiver row (shelf-86uh)
---

# 0018 — A checkpoint is enforced from the pin; a waiver is the only way to wait

## Decision

- **The pin is the rollout.** A consumer pins the whole shelf by one blueprint tag. The set of checkpoints it is
  judged by cannot change until someone bumps that tag. At the bump the repo sees every new checkpoint and fixes it
  or waives it. There is no "warn until the next audit" state and no baseline file.
- **A waiver is explicit, dated and in the repo.** A repo waives a checkpoint in its own config:

  ```toml
  [[tool.blueprint.waivers]]
  id = "stack.compose.dependencies"
  reason = "digest pinning moves to the rendered image-pins step in the next release"
  until = "2026-12-31"      # at most 90 days out; the audit fails a later date
  ```

  A waived checkpoint shows as a waiver (with the days left) and does not fail. A waiver past its `until`, a
  waiver with no reason, and a waiver for a checkpoint the pinned engine does not know all fail the gate.
- **The audit writes nothing tracked.** `blueprint check` prints its report. `--write` puts the narrative reports in
  an ignored folder (`.blueprint/reports/`), never under `docs/`. `docs/blueprint/checkpoints.txt` is not read any
  more; a repo deletes it, and the per-section Markdown reports it holds under `docs/blueprint/`.

Why: the shelf moving must not turn every consumer's pre-push red in the middle of unrelated work
(a2kay, 2026-10-11: `uv lock --check` landed and blocked its push). The pin already guarantees that, because a
rule set cannot change under a repo that did not bump. The old baseline list added a second state and a file every
repo had to keep; a repo that never audited (a2kay) stayed soft forever, and a failing row hid as a warning until
someone ran the audit.

## Rejected

- The baseline list `checkpoints.txt` with 🆕 warnings (the 2026-10-11 decision): a second state and a tracked file
  for what the pin already gives; no clock, so a repo that never audits is never held to a new row.
- A version per rule with consumer pinning: per-rule bookkeeping for the same effect.
- A global "warn for N releases" clock in the engine: the same soft state, owned by the shelf instead of the repo,
  and it hides which repo is actually waiting.
- Enforce with no waiver: strict, but a repo cannot ship a bump that needs one rule fixed in a later change.

## Consequences

- A release that adds a checkpoint is a corpus event: the corpus diff already reports every repo's verdict change,
  and a new checkpoint that would fail a pinned consumer is stated in the changelog.
- A repo that tracks a branch of the shelf instead of a tag has no pin and gets new checkpoints at once. None does
  today (every consumer pins a tag); a repo that does not must pin before it can use a waiver.

## History

- 2026-10-11: decided (shelf-pqu). Each audit recorded the judged checkpoints in `docs/blueprint/checkpoints.txt`;
  the gate enforced that set and a newer checkpoint only warned (🆕).
- 2026-11-05: note (ADR 0028). Warn-first is a rollout rule for consumer repos, not a code path: no warn-mode exists in code.
- 2026-11-28: rewritten (owner: the list is dead weight next to the pin). a2kay audit: no list, 54 KB of stale
  narrative reports, two new rows that warned for weeks. Reviewers (Opus, Fable) judged the missing clock a defect.
  The list and the 🆕 state go; waivers with an expiry replace them (shelf-86uh).
