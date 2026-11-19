# Gate test loop: run the tests a change reaches, once

Owner: shelf gate. Source: `docs/thoughts/2026-11-19-gate-and-blueprint-overhaul-menu.md` (measured facts and the full menu).
Depends on `gate-kit-package` for where the code lives; this change says what the loop does.

## Why

Measured 2026-11-19 on the shelf at fad2bb8:

- 45 of the last 50 commits touch `uv.lock` (a release bumps a version) and `tools/affected.py` treats a lock change as
  "select everything", so the changed-only gate and its pass cache are defeated on nearly every real commit (median 79 of 79
  package suites; the same 50 commits select a median 1.5 when the lock is read per package).
- A test run takes 92 s for all 79 suites and a clean-diff gate takes 10-16 s on an idle 14-core box. On the loaded Mac the same gate
  took 818 s, of which 789 s was waiting for the box-wide test lock. The cost is queueing and repetition, not test volume.
- A change is tested up to three times: the agent's `just check`, the pre-push gate, `check-all` before a tag. The pre-push skip works only
  for a byte-identical tree, so an amend or rebase reruns everything.
- Selection had a hole: two packages' tests imported `async-scope` without declaring it (fixed, with a fitness test). A hub mutation also
  failed one blueprint test that was not selected; it passed in 25 solo runs, in the original pair and in 6 parallel runs, so that failure is
  unexplained and unreproduced. Full parallel runs are flaky: `process-lock` once (root cause found and fixed: a leaked lease in `any-lease` tests polluted the process-wide lock registry), and `any-lease`
  `test_sigterm_reaches_the_command...` in 1 of 3 runs (not reproduced since).
- `main` was red on a clean diff (stale generated READMEs): an ungated squash merge lands a tree no local gate saw.

## What changes

1. **Selection reads the lock per package.** A package is touched when its own files change or when `uv export` of its runtime and
   dev set changes; dependants follow through the existing graph. "Lock changed" no longer selects everything.
2. **Selection is exact for declared edges, and a fitness test proves the declarations are true**: every workspace-internal import
   is a declared dependency; fix the two undeclared edges.
3. **Flaky tests cannot block the gate**: a `quarantine` lane for known flakes plus a fix per flake; a check that no package test reads outside its own
   package or a temp dir, if the hits found (8 in `packages/blueprint/tests`) prove to read the live checkout.
4. **Receipts**: a green result is stored under a key of its closure (selected tests, their inputs, toolchain, python/uv versions) and
   reused by the pre-push hook, the agent's manual run and a rebase. A failed run is never a receipt.
5. **Run guard**: worker cap from cores, RAM and test count; one process for small selections; wall and idle limits that kill the
   process tree; `serial` and `quarantine` markers (a quarantined test cannot block); `nice` for non-landing runs; a "selection reaches
   too far" alarm; a `reach` report of suites selected per recent commit.
6. **Hooks run each thing once**: commit hook = bd hooks plus linters on staged files; pre-push = the gate, skipped by receipt;
   the full run with the coverage floor on tag. Tests never run in the commit hook.
7. **Ungated merges are covered**: a `post-merge` gate run (or a required `just check` before each tag) with the decision recorded
   against ADR 0027 (no CI).
8. **Pytest only.** The gate runs `pytest` for tests; coverage is measured by pytest on the full run only.
9. **Test environments**: each package declares its own test dependencies; heavy extras (torch, transformers, llama, browser) are
   opt-in lanes. Whether tests run in isolated per-package venvs is decided in the design from a measurement, not assumed.

## Not in this change

Where the code lives and its CLI (`gate-kit-package`); what blueprint enforces (`blueprint-multi-stack-contracts`); the second
language for shelf packages (ADR 0021's trigger is handled in `gate-kit-package`).

## Superseded and amended

ADR 0021 ("affected-only tests stay on tools/affected.py") is amended by `gate-kit-package`, which replaces the script. ADR 0027
(no CI) stays; item 7 works inside it.
