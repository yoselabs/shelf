---
id: 0027
title: The shelf has no CI; the local gate is the gate
statement: The shelf runs no CI. Done is the local `just check` (the container gate) green on the tree pushed; the pre-push hook enforces it. A macOS-only change is run on the macOS host.
concerns: [gate, workflow]
status: accepted
decided_by: owner
updated: 2026-11-04
distilled_into: N/A — self-enforcing via the pre-push hook running `just check` and the gate.ci override in docs/blueprint/blueprint.toml
---

# 0027 — The shelf has no CI

## Decision

- No GitHub Actions workflow. `.github/workflows/check.yml` (jobs `check`, `gate-image`, `stream-proc-macos`) is removed.
- The gate is `just check` (container when Docker answers, host otherwise), run by the pre-push hook on the
  tree being pushed. `just check-all` is run locally before a release tag.
- `gate.ci` is excused by an adr-backed override ([ADR 0022](0022-every-exception-is-justified.md)); `gate.ci-green`
  has no workflow to read and reports not-applicable.
- The macOS-only `stream-proc` probe (libproc through ctypes) is no longer run by a job: a change to it is run on
  the owner's macOS host (`uv run pytest packages/stream-proc`) before its tag.

Why: waiting for CI blocked merges for 5 to 15 minutes after the same gate had already passed locally and in the
push hook; the owner builds and merges from machines that run it.

## Rejected

- Keep CI as advisory: a red job nobody waits for is noise, and it still costs a run per push.
- Keep only the macOS job: it is the one thing the container gate cannot see, but one probe does not need a pipeline; the manual run above covers it.

## History

- 2026-11-04: decided by the owner ("remove ci workflow, I approve it. we don't want to wait for ci").
