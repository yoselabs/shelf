# Tasks

Blocked on `fix-guard-hookspath-resolution` (D6) — it supplies the first verify-by-behavior
implementation this change generalizes. Do not start section 2 before it lands.

Tests-first per the working agreement. `make check` green across the whole repo is Done.

## 0. Setup
- [ ] 0.1 File this change as a bead; add a `blocks` dependency on `shelf-efh`'s change so the
      sequencing in D6 is enforced by the queue, not by memory.
- [ ] 0.2 Confirm `fix-guard-hookspath-resolution` has landed and its verifier is callable.

## 1. The contract document
- [ ] 1.1 Write `docs/runbooks/repo-bootstrap.md`: the four obligations (idempotent, ordered,
      verifying, honest), the three-outcome rule, and the minimum assertion table from D3.
- [ ] 1.2 Include a reference `Makefile` fragment — illustrative, explicitly not normative
      (D1: the obligation is shared, the implementation is not).
- [ ] 1.3 State the read-only rule for `bootstrap-verify` (design open question 1): the gate
      observes, `bootstrap` repairs. A gate that silently fixes drift hides it.

## 2. `make bootstrap` (needs section 0.2)
- [ ] 2.1 Failing test: running `bootstrap` twice from a clean clone produces identical repo
      state the second time. Idempotency is the property most likely to rot, so it gets a test
      before an implementation exists to satisfy it.
- [ ] 2.2 Implement the target with ordering as prerequisites (D2), each non-obvious edge
      carrying the finding that justifies it as a comment.
- [ ] 2.3 Failing test: with `pre-commit` configured, `bootstrap` installs it *before* `bd init`
      — assert on resulting state (bd chained into a native hook; `core.hooksPath` unset),
      not on invocation order.

## 3. `make bootstrap-verify`
- [ ] 3.1 Wire the **content** assertion into `make check` — but only if `shelf-gag` has not
      already done it (it should have; it is P1 and unblocked). If it has, verify the wiring
      matches D4's split and move on rather than duplicating it.
- [ ] 3.2 Failing test per assertion in D3's table: hook-blocks-offending-state,
      config-reads-back, hooks-reachable-by-git, no-slot-contention. Each must fail for the
      right reason before it passes.
- [ ] 3.3 Failing test: an unverifiable environment reports **could-not-check**, distinct in
      both exit code and message from both pass and fail (D3).
- [ ] 3.4 Failing test: `bootstrap-verify` is read-only — run it against a repo with unrelated
      uncommitted changes and misconfigured hooks; assert it reports failure and that git
      config, the index, and tracked files are byte-identical afterwards.
- [ ] 3.5 Failing test: `make check` passes on a clone with no hooks installed and no tooling
      configured, provided its content is clean — the gate must not require bootstrap (D4).
- [ ] 3.6 Confirm `make check` does **not** depend on `bootstrap-verify`, and that no
      CI-specific mode or skip flag was needed to achieve that.

## 4. Rewrite the beads runbook (D5)
- [ ] 4.1 Convert each instruction to an assertion, per D5's table. Work rule by rule; do not
      rewrite prose wholesale.
- [ ] 4.2 Audit against D5's stated exception: findings *about bd's behavior* stay prose;
      only lines that read as a task assigned to the reader convert.
- [ ] 4.3 Verify nothing was lost — every "verified on <repo>, <date>" attribution and every
      finding survives the rewrite. Diff old against new specifically for dropped evidence;
      a voice change must not become a content cull.
- [ ] 4.4 Confirm self-containment: a reader adopting beads can follow it end to end without
      reading `repo-bootstrap.md` first.

## 5. Entry points
- [ ] 5.1 `AGENTS.md`: `make bootstrap` as the first move on an unfamiliar clone.
- [ ] 5.2 `docs/consuming-the-shelf.md` §2: replace the manual `install.py` invocation with
      `make bootstrap`; keep the manual path documented for repos with no Makefile.

## 6. Close the loop (resolution 0009)
- [ ] 6.1 `make check` green, whole repo.
- [ ] 6.2 Confirm `shelf-gag` closed on its own (it is independent of this change now); if it
      is still open, this change should not close it.
- [ ] 6.3 Ledger row.
- [ ] 6.4 Merge and push.
