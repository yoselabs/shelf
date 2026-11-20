---
id: 0027
title: No repository has GitHub Actions CI; the local gate is the gate
statement: No repository holds GitHub Actions configuration. Done is the local `just check` green on the tree pushed and on a merged tree; blueprint's `gate.no-ci` fails a repo with workflows.
concerns: [gate, workflow]
status: accepted
decided_by: owner
updated: 2026-11-20
distilled_into: blueprint gate.no-ci; the pre-push and post-merge hooks running `just check`
---

# 0027 — No repository has GitHub Actions CI

## Decision

- No repository has GitHub Actions configuration: no `.github/workflows/*.yml|yaml`, no composite action under
  `.github/actions`. This holds for the shelf and for every consumer app.
- The gate is `just check` (native, one way), run by the pre-push hook on the
  tree being pushed. `just check-all` is run locally before a release tag.
- A `post-merge` hook runs the same gate on a merged tree (a pull of a merge made on GitHub), skipped when that tree already passed. It cannot
  undo the merge; it reports at once what no local gate saw.
- Blueprint enforces it: `gate.no-ci` fails when a repo holds Actions configuration. Its remedy is to delete the files. A duty a
  workflow carried that is not CI (image publish, deploy, scheduled evals) moves to a local command or waits for an owner decision; it
  is never kept in a workflow.
- Every blueprint row that only existed to judge CI is gone: `gate.ci`, `gate.ci-no-manifest-edit`, `gate.ci-green`, the python-uv
  `python-range-tested`, `python-ci` and `uv-ci` (the image half of `uv-ci` lives on as `uv-images`), the framework `ci` roles, the
  dockerfile `ship-smoke` row, and the facts read from workflow files (`ships-image`, `deployed`, `scheduled-jobs` are traits the agent
  classifies).
- Onboarding never creates a workflow.
- The macOS-only `stream-proc` probe (libproc through ctypes) runs in the native gate with the other tests.

Why: waiting for CI blocked merges for 5 to 15 minutes after the same gate had already passed locally and in the
push hook; the owner builds and merges from machines that run it. On 2026-11-20 the owner extended that from the shelf to every repository.

## Rejected

- Keep CI as advisory: a red job nobody waits for is noise, and it still costs a run per push.
- Keep only the macOS job: the gate now runs on the Mac itself, so a job would repeat it.
- A per-repo override of the no-CI rule: the policy is the owner's, not each repo's; a repo that wants a workflow asks the owner.

## History

- 2026-11-04: decided by the owner for the shelf ("remove ci workflow, I approve it. we don't want to wait for ci").
- 2026-11-05: the container gate is gone (Docker purged: 10-minute image builds, disk pollution); `just check` runs natively on the Mac, one way. Linux and Windows return later as matrix legs, not gate modes.
- 2026-11-19: added the post-merge gate: a GitHub squash merge pulled into `main` was red on a clean diff (stale generated READMEs), because no gate ever ran on the merged tree.
- 2026-11-20: widened from "the shelf has no CI" to "no repository has GitHub Actions CI" (owner policy). `gate.ci` (which required CI and was overridden here) is inverted into `gate.no-ci`.
