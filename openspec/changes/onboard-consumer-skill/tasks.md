# Tasks

Blocked on `shelf-efh` — the `guard` operation is `tools/hooks/install.py`, and it must resolve
hook paths correctly before anything can depend on its verification.

Tests-first. `make check` green, whole repo, is Done.

## 0. Setup
- [x] 0.1 Confirm `shelf-efh` has landed and `install.py` verifies liveness. (closed, `db6575f`)
- [ ] 0.2 Re-scope `shelf-abf` (`bootstrap-target-contract`): `make bootstrap` becomes a caller of
      these operations, not a competing implementation. Update its proposal and its bead's
      dependency direction — it now depends on this change, not the reverse.

## 1. The operation contract (D3)
- [x] 1.1 Failing test per guarantee, against a trivial reference operation, before any real
      operation exists: idempotent, precondition-checked, effect-asserting, three-outcome,
      non-destructive. The contract is the deliverable here; the operations are instances.
      (`tests/test_onboard_operations.py`)
- [x] 1.2 Implement the shared operation harness — result type carrying the three outcomes,
      precondition declaration, and the "verified" flag a dependent operation reads.
      (`tools/onboard/operations.py`)
- [x] 1.3 Failing test: an operation whose precondition is *present but unverified* is refused.
      This is the distinction the whole design rests on (D3 guarantee 2 vs 3) — a hook file
      existing must not satisfy "guard is installed". Landed as
      `test_present_but_unverified_dependency_still_blocks_the_dependent` — the harness
      withholds the call entirely rather than trusting each operation to self-check
      (`test_harness_withholds_the_call_rather_than_trusting_the_operation_to_self_check`).

## 2. Stack-agnostic operations
- [x] 2.1 `guard` — wrap the `shelf-efh` installer as an operation; do not reimplement it.
      (`tools/onboard/guard.py`, subprocess around `tools/hooks/install.py`, exit code ->
      Outcome mapping; `tests/test_onboard_guard.py`)
- [x] 2.2 `resolver-block` (D5) — marker-delimited projection into `AGENTS.md`. Failing tests:
      writes when absent; rewrites in place when the source changed; is a no-op when current;
      appends **outside** every pre-existing managed block (bd leaves two in this repo);
      handles a symlinked `CLAUDE.md` without following or clobbering it.
      (`tools/onboard/resolver_block.py`, `tests/test_onboard_resolver_block.py` — 6 tests)
- [x] 2.3 `beads` — `bd init`, config with readback, `bd dolt push` chained outside bd's markers.
      Failing test: refuses to run when `guard` has not completed and verified (landmine 1).
      (`tools/onboard/beads.py`, `tests/test_onboard_beads.py` — 4 tests against the real `bd`
      binary, no mocking; skipped when `bd` is absent). Verification is partial and says so in
      the module docstring: `sh -n` on the appended hook, not a live `bd dolt push` (would need a
      real Dolt remote and touch the network as an onboarding side effect).
- [x] 2.4 Failing test for the config-revert trap (landmine 5): after `bd config set`, a
      `git checkout -- .beads/config.yaml` makes `verify` fail rather than silently pass.
      Landed as self-heal-and-report-truthfully rather than a bare FAILED: `verify` re-runs the
      operation (D3.1 idempotence), which re-executes `bd config set` + `bd config get` from
      scratch — the revert is caught AND fixed in the same pass, never silently missed. A
      read-only check would only have reported the drift; this converges past it, which is
      strictly more useful for an onboarding tool.
      (`test_config_revert_is_caught_and_self_healed_by_a_second_verify_pass`)
- [x] 2.5 `verify` — assert every applied operation is live; report per-operation, not one
      aggregate boolean.
      (`tools/onboard/verify.py`: `verify()` = `run_all()` re-invoked — "re-running IS
      re-verifying" is the whole mechanism, no separate check path to drift from apply.
      `all_satisfied()` is an explicit opt-in aggregate, never the default return shape.
      `tests/test_onboard_verify.py` — 3 tests)

## 3. Python + uv operations
- [x] 3.1 `linter-preset` — ruff/codespell/coverage blocks, Makefile targets, dev group.
      (`tools/onboard/linter_preset.py`)
- [x] 3.2 Failing test: merges into an existing `pyproject.toml`/`Makefile` rather than
      overwriting; a repo with its own ruff config keeps its overrides (resolution 0004's
      "copy, then own" must survive re-running onboarding). Merge granularity is per-family
      (owning `[tool.ruff]` at all — even one overridden key — takes the whole ruff namespace
      off the table, `[tool.ruff.lint]` included; same for `tool.coverage.*`), never per-line —
      per `docs/linting.md`'s own "own it" framing, line-level reconciliation is the consumer's
      judgment, not this operation's to make.
      (`tests/test_onboard_linter_preset.py` — 6 tests)
- [x] 3.3 Confirm the stack tag is real: the stack-agnostic operations run to completion against
      a target repo with no `pyproject.toml` at all, and `linter-preset` reports
      could-not-apply rather than failing the run.
      (`test_no_pyproject_is_could_not_apply_not_a_failure`; the stack-agnostic operations
      (`guard`/`resolver-block`/`beads`/`verify`) have no dependency on `pyproject.toml` at all,
      so nothing else in the run is blocked by `linter-preset`'s COULD_NOT_APPLY.)

## 4. The skill (D4)
- [ ] 4.1 Decide the skill's location (design open question 2), biased to the cross-tool path.
- [ ] 4.2 Author the skill: detection, the decision table, invocation, and reporting. Authored via
      the skill-authoring pipeline, per the onboarding mission's own rule ("never hand-waved").
- [ ] 4.3 Audit against D4's must-not list — no ordering in the skill text, no verification
      verdicts of its own, no adding shelf dependencies.
- [ ] 4.4 Exercise it end to end on a scratch greenfield repo: empty repo → shelf consumer +
      beads → `verify` green → a seeded local `path=` source is blocked. This is the acceptance
      test for the whole change; if it does not run clean, nothing else here matters.
- [ ] 4.5 Exercise the adaptive paths on scratch repos: already has pre-commit framework; already
      has husky; already ran `bd init`; is not Python; is already fully onboarded (expect a clean
      no-op).

## 5. Documentation collapse
- [ ] 5.1 `docs/consuming-the-shelf.md` — stays the description of what a consumer *is*; the
      mechanical steps point at the skill.
- [ ] 5.2 `docs/runbooks/onboard-a-consumer.md` — drop Phase A's duplication; keep the catch-up
      sweep, which is genuinely different work.
- [ ] 5.3 `docs/runbooks/adopt-beads.md` — beads becomes part of onboarding; the runbook keeps
      every finding as the justification for the assertions (`bootstrap-target-contract` D5's
      voice rule applies here too).
- [ ] 5.4 `docs/missions/onboarding-new-micro-software.md:44` — correct the "consumer half: DONE"
      claim, stating what was actually missing rather than deleting the line.

## 6. Close the loop (resolution 0009)
- [ ] 6.1 `make check` green, whole repo.
- [ ] 6.2 File a bead for re-onboarding a2kay and a2web (design open question 1) — do not do it
      inside this change.
- [ ] 6.3 Ledger row.
- [ ] 6.4 Merge and push.
