# Blueprint: outcome contracts across several stacks

Owner: blueprint. Source: `docs/thoughts/2026-11-19-gate-and-blueprint-overhaul-menu.md`. Pairs with `gate-test-loop` (what the loop does)
and `gate-kit-package` (where the code lives).

## Why

What blueprint is today (read from `packages/blueprint/src/blueprint/profile.py` and `profiles/*.toml`):

- Detection already finds several stacks in one repo (`python-uv`, `python`, `dotnet`, `nix`, `compose`, `dockerfile`, `shell`, `node`, `go`,
  `rust`; `profile.stacks` is a tuple). But only six stacks have a profile file (`python-uv`, `shell`, `dockerfile`, `compose`, `dotnet`,
  `nix`) plus three frameworks. `node`, `go` and `rust` are detected and then checked against nothing, so a Node-plus-Python repo gets
  Python checks only.
- A profile is a list of roles (toolchain, formatter, linter, types, tests, coverage, architecture, hooks, ...) whose `gate` field is a
  regex that must appear in the text of `just check`. That enforces the shape of a command, not an outcome. Python `tests` demands pytest
  inside `just check`; `coverage` demands pytest-cov's `--cov-fail-under`. Both consumers had to override or ignore these (a2kay: an
  override plus shelf-2hl; task-loop ran affected-only tests as a separate step and ignored the finding).
- Every profile has an `architecture` role (layering): import-linter plus ruff TID251 for Python; four layers for .NET; and so on. That is
  right, and it must hold for every new stack too.
- Secrets: the one concern is sops ("a sealed file is really sealed"). Nothing scans content. Task-loop added gitleaks to its gate and
  reverted it the same day.
- Overrides already require a reason and an expiry or an accepted ADR, and an expired override stops excusing its checkpoint. The gap is
  no warning before expiry.
- Reports are written to `docs/blueprint/` and committed per run: a2kay made 15+ blueprint commits in about three weeks, each with a report.
- Three copies of the same scripts exist (shelf `tools/`, blueprint `recipes/`, each consumer).

## What changes

1. **Outcome contracts replace command-shape checks.** A role states the outcome it needs (for tests: "the tests the change reaches ran green,
   or a receipt exists for the same closure; the full run with coverage happens on tag") and the stack adapter says how that is proven.
   The regex-in-`just check` match survives only as one way to prove it.
2. **Stack adapters.** Each stack supplies the same small set of capabilities: list the units, build the unit dependency graph, select
   the units a change reaches, run their tests, lint, and enforce layering. Python's adapter uses `pyproject.toml`, `uv export` and pytest.
   Adding a stack means adding an adapter and a profile; the neutral core does not change.
3. **Mixed stacks are first class.** `blueprint check` and `blueprint test` run every declared stack's steps in one gate; a change is selected
   per stack, and a cross-stack edge is declared, never inferred. Profiles for `node`, `go` and `rust` are added (each with a layering role).
   Proposed opinionated layout for a mixed repo: each unit in its own folder with one manifest, one lock per ecosystem, one gate at the root,
   no cross-stack import except through a declared contract (a schema, a CLI, a generated file). To be decided by the owner (see design).
4. **Layering is mandatory for every stack.** A stack profile without an `architecture` role fails blueprint's own fitness test.
5. **Secret scanning on the changed range** (staged files in the commit hook, the diff range in the gate, a full scan on tag) with a standard
   scanner pinned in `mise.toml`; the sops concern stays.
6. **Hook anti-patterns are findings with a fix**: tests in the commit hook; the gate duplicated by hand and by hook; the hook path taken by
   another tool; a hook that cannot fail; a guard that lives outside the repo.
7. **Less churn**: reports are committed only when a verdict changes; checkpoints carry an input fingerprint so an unchanged one is not
   rerun; converge mode batches at most one commit per shelf bump; override expiry warns a set time before it lands.
8. **Cut checkpoints no consumer needs.** Candidates from a2kay and task-loop: the pytest-cov-only coverage check, `cli-parse`,
   the python-range pin, and the Dockerfile/compose tool pile as a gate step. Each goes or is justified by a live consumer (constitution:
   protection is earned).
9. **The `justfile` is rendered from the declared stacks** and drift-checked by re-rendering and comparing, replacing the justfile part of
   `tools/preset_drift.py`.

## Not in this change

The receipt and selection machinery (`gate-test-loop`); the package and CLI home (`gate-kit-package`).

## Amended

ADR 0023 (gate runner is just) stays: the rendered justfile calls the `blueprint` verbs. ADR 0004 (linters are a config preset, not a CLI)
stays for lint configuration; this change moves gate orchestration, not lint rules. ADR 0018 (a new checkpoint warns until the next
audit) governs rollout of each new checkpoint.
