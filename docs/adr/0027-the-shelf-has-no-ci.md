---
id: 0027
title: The shelf has no CI; the local gate is the gate
statement: The shelf runs no CI. Done is the local `just check` green on the tree pushed and on a merged tree after a pull; the pre-push and post-merge hooks run it.
concerns: [gate, workflow]
status: accepted
decided_by: owner
updated: 2026-11-19
distilled_into: N/A — self-enforcing via the pre-push hook running `just check` and the gate.ci override in docs/blueprint/blueprint.toml
---

# 0027 — The shelf has no CI

## Decision

- No GitHub Actions workflow. `.github/workflows/check.yml` is removed.
- The gate is `just check` (native, one way), run by the pre-push hook on the
  tree being pushed. `just check-all` is run locally before a release tag.
- A `post-merge` hook runs the same gate on a merged tree (a pull of a merge made on GitHub), skipped when that tree already passed. It cannot
  undo the merge; it reports at once what no local gate saw.
- `gate.ci` is excused by an adr-backed override ([ADR 0022](0022-every-exception-is-justified.md)); `gate.ci-green`
  has no workflow to read and reports not-applicable.
- The macOS-only `stream-proc` probe (libproc through ctypes) runs in the native gate with the other tests.

Why: waiting for CI blocked merges for 5 to 15 minutes after the same gate had already passed locally and in the
push hook; the owner builds and merges from machines that run it.

## Rejected

- Keep CI as advisory: a red job nobody waits for is noise, and it still costs a run per push.
- Keep only the macOS job: the gate now runs on the Mac itself, so a job would repeat it.

## History

- 2026-11-04: decided by the owner ("remove ci workflow, I approve it. we don't want to wait for ci").
- 2026-11-05: the container gate is gone (Docker purged: 10-minute image builds, disk pollution); `just check` runs natively on the Mac, one way. Linux and Windows return later as matrix legs, not gate modes.
- 2026-11-19: added the post-merge gate: a GitHub squash merge pulled into `main` was red on a clean diff (stale generated READMEs), because no gate ever ran on the merged tree.
