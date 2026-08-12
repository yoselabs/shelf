# Tasks

Both blockers landed: `fix-guard-hookspath-resolution` (shelf-efh) and `onboard-consumer-skill`
(shelf-n63). See `design.md`'s 2026-08-12 addendum — it resolves most of D1–D6 by already being
the thing D1 anticipated. What's left is genuinely small: wire `make bootstrap` /
`make bootstrap-verify` to the operations that already exist, and update the surrounding docs.

Tests-first. `make check` green across the whole repo is Done.

## 0. Setup
- [x] 0.1 File this change as a bead; dependency on `shelf-efh` enforced by the queue.
      (`shelf-abf`, already depended on `shelf-n63` per its own re-scope.)
- [x] 0.2 Confirm `fix-guard-hookspath-resolution` and `onboard-consumer-skill` have landed.

## 1. The contract document — superseded, do not write `repo-bootstrap.md`
- [x] 1.1–1.3 as originally scoped (a from-scratch obligations doc, a reference Makefile
      fragment, the read-only rule) are superseded: the obligations are `tools/onboard/
      operations.py`'s D3 guarantees (already documented in its own module docstring, and in
      `onboard-consumer-skill`'s design.md D3), and the "reference Makefile fragment" is
      literally the `bootstrap`/`bootstrap-verify` targets added to shelf's own `Makefile` below
      — copied verbatim into a consumer the same way `guard:` already is (`docs/linting.md`'s
      copy list), not a separate prose document repeating what the operations' docstrings say.
      Writing `docs/runbooks/repo-bootstrap.md` now would be exactly the "instructions for a
      reader" this whole design line was arguing against duplicating in Make form.

## 2. `make bootstrap`
- [x] 2.1 Failing test: running `bootstrap` twice from a clean clone produces identical repo
      state the second time. `test_make_bootstrap_is_idempotent_at_the_target_level`
      (`tests/test_bootstrap_target.py`), against a real `make -C <scratch-repo> bootstrap`.
- [x] 2.2 Implement the target. Ordering is NOT a Make prerequisite graph (D2's addendum): a
      single target delegates to `tools/onboard/`'s operations via
      `.agents/skills/onboard-consumer/scripts/onboard.py`, which already enforces ordering
      through `run_all()`. (`Makefile`'s `bootstrap`/`bootstrap-verify` targets.) Found and fixed
      a real bug while wiring this: the script resolved its own `shelf_home` for imports but
      never propagated it as `$SHELF_HOME` to `GuardOperation`'s internal subprocess call to
      `tools/hooks/install.py`, which could silently resolve a *different* shelf clone than the
      one the script was actually running operations from.
- [x] 2.3 Failing test: with a foreign hook manager (pre-commit framework / husky / lefthook)
      already configured, `bootstrap` does not clobber it and reports which tool owns the slot.
      `test_make_bootstrap_does_not_clobber_a_foreign_hook_manager`
      (`tests/test_bootstrap_target.py`).
- [x] 2.4 (not originally scoped, added for real) `make bootstrap` run inside the shelf's own
      repo refuses rather than projecting the resolver block into shelf's own `AGENTS.md` —
      `test_refuses_to_onboard_the_shelf_onto_itself` (`tests/test_onboard_script.py`); also
      confirmed live: `make bootstrap` in this repo prints the refusal and exits 2.

## 3. `make bootstrap-verify`
- [x] 3.1 Confirm the **content** assertion is wired into `make check` via `shelf-gag` (closed,
      independent, as D4 predicted) — it is (`guard` target, `Makefile:10`). Nothing to duplicate.
- [x] 3.2 Assertion coverage per D3's table already exists at the operation level (see design.md
      addendum's D3 bullet for the exact mapping) — the Makefile target
      (`bootstrap-verify: bootstrap`) calls the operations and surfaces per-operation results;
      `test_make_bootstrap_verify_is_the_same_call_under_a_different_name`
      (`tests/test_bootstrap_target.py`).
- [x] 3.3 Could-not-check stays distinct: `Outcome.COULD_NOT_APPLY`, already a separate case from
      both `APPLIED` and `FAILED` throughout `tools/onboard/`.
- [x] 3.4 `bootstrap-verify` is intentionally NOT read-only — this is a resolved deviation from
      the original open question, not an unmet task; see design.md's addendum to "Open questions".
- [x] 3.5 Failing test: `make check` passes on a clone with no hooks installed and no tooling
      configured, provided its content is clean — the gate must not require bootstrap.
      `test_make_check_does_not_depend_on_bootstrap` (`tests/test_bootstrap_target.py`).
- [x] 3.6 Confirm `make check` does **not** depend on `bootstrap-verify` after this change's
      Makefile edits land, and that no CI-specific mode or skip flag was needed. Confirmed —
      `check:`'s prerequisite list (`Makefile:10`) is unchanged by this section.

## 4. The beads runbook — already done, differently than sketched
- [x] 4.1–4.4 Superseded by `onboard-consumer-skill` §5.3: `adopt-beads.md` kept its voice and
      gained one intro paragraph stating the `beads` operation performs what it describes
      automatically. Every finding, every "verified on <repo>, <date>" attribution, and
      self-containment all survive intact (that was §5.3's own acceptance bar). A full per-line
      instruction-to-assertion rewrite would duplicate work already judged complete.

## 5. Entry points
- [x] 5.1 `AGENTS.md`: point at `make bootstrap` as the fast path for an unfamiliar clone that
      wants to consume the shelf (this repo's own `AGENTS.md` doesn't need this — it IS the
      shelf, and `make bootstrap` there refuses by design — so this lands in the reference doc a
      consumer copies from instead: `docs/consuming-the-shelf.md` §2,
      `docs/runbooks/onboard-a-consumer.md` Phase A).
- [x] 5.2 `docs/consuming-the-shelf.md` §2: note `make bootstrap` as the one-command path once a
      consumer has copied the Makefile targets (§4, `docs/linting.md`); keep
      `python "$SHELF_HOME/.../onboard.py"` documented for a repo that hasn't copied the
      Makefile yet (mirrors the existing "manual `install.py`" note, doesn't replace it — a
      consumer without a Makefile fragment yet still needs a way in).
      `docs/linting.md`'s copy list and per-target guidance updated too (`bootstrap`/
      `bootstrap-verify` added to the target list and to `tools/onboard/linter_preset.py`'s
      `_MAKE_TARGETS`, so a consumer running `linter-preset` actually gets them copied, not just
      documented).

## 6. Close the loop (resolution 0009)
- [x] 6.1 `make check` green, whole repo.
- [x] 6.2 Confirm `shelf-gag` closed on its own — it is, independent of this change.
- [x] 6.3 Ledger row.
- [x] 6.4 Merge and push.
