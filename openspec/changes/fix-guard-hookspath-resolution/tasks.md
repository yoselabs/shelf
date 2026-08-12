# Tasks

Tests-first per the working agreement: each behavioral task lands its failing test before
its implementation. `make check` green across the whole repo is the only Done.

## 0. Setup
- [ ] 0.1 Claim the bead: `bd update shelf-efh --claim` and record provenance
      (`bd update shelf-efh --set-metadata branch=<name>`).
- [ ] 0.2 Confirm the bug still reproduces on a clean checkout before changing anything —
      set `core.hooksPath`, install the guard, stage an offending `path=` source, commit,
      observe it is **not** blocked. A fix for a bug you haven't re-witnessed is a guess.

## 1. Path resolution (D1)
- [ ] 1.1 Failing test: with `core.hooksPath` set to a temp dir, the installer writes the
      guard into *that* dir, not `.git/hooks`. Use a real `git init` + `git config` in a
      tmpdir — not a mock; the whole bug was a wrong belief about git's behavior.
- [ ] 1.2 Failing test: with `core.hooksPath` unset, behavior is unchanged (`.git/hooks`).
      This is the regression guard for every existing consumer.
- [ ] 1.3 Replace `hooks = git_dir / "hooks"` with `git rev-parse --git-path hooks`,
      keeping the relative→absolute normalization.
- [ ] 1.4 Delete the now-unused `_git_dir()`.

## 2. Liveness verification (D2)
- [ ] 2.1 Failing test: installer exits non-zero when the resolved hook does not actually
      block an offending state. Simulate by pointing `core.hooksPath` at a dir git won't
      execute from, or by neutering the written hook after install.
- [ ] 2.2 Failing test: a successful install reports **verified live**, and a run where
      verification cannot execute (guard script absent — `HOOK`'s `exit 0` branch) reports
      **unverified** with a distinct exit code and message. Three outcomes, three signals.
- [ ] 2.3 Implement verification: seed an offending state, invoke the resolved hook as git
      would, require non-zero exit, restore.
- [ ] 2.4 Assert the cleanup constraint explicitly (D2): verification must not mutate the
      index, tracked files, or commits — no `git reset --hard`, no `git stash`. Add a test
      that a dirty-but-unrelated working tree is byte-identical before and after a run.

## 3. Foreign-hook diagnosis (D3)
- [ ] 3.1 Failing test per manager: a `.beads`-managed, husky, lefthook, and pre-commit
      hook each produce a refusal naming that manager and its correct extension point.
      Table-driven — one marker fixture per row of D3's table.
- [ ] 3.2 Failing test: an unrecognized foreign hook still gets the current generic advice
      (no regression for the hand-written case).
- [ ] 3.3 Implement marker detection + messages. Note in the pre-commit-framework message
      that the guard already works there (ledger 0038) and no action is needed.

## 4. Docs (D4 + the runbook inversion)
- [ ] 4.1 `docs/consuming-the-shelf.md` §2: the installer's success now means verified-live;
      state plainly that **existing clones remain unguarded until re-run**, and that
      re-running is the only remedy.
- [ ] 4.2 Same file: record that hooks under an in-tree `core.hooksPath` (beads'
      `.beads/hooks`) are tracked and DO travel with a clone — the section's "hooks are
      per-clone and cannot be committed" premise has an exception now.
- [ ] 4.3 `docs/runbooks/adopt-beads.md`: cross-reference this change from the
      `core.hooksPath` section, so the next adopter meets the fix, not just the hazard.

## 5. Close the loop (resolution 0009)
- [ ] 5.1 Re-arm this repo's own clone and verify live — it is currently unguarded.
- [ ] 5.2 `make check` green, whole repo, no carve-outs.
- [ ] 5.3 `bd close shelf-efh`; confirm `shelf-gag` leaves `bd blocked` and appears in
      `bd ready`.
- [ ] 5.4 Append a `ledger/00NN-<slug>.toml` row. This is a `verification`-flavored entry
      as much as a delivery — the finding was "a guard reported green while dead", which
      is exactly what the ledger exists to record.
- [ ] 5.5 Merge to `main` and push. Note the push fires `bd dolt push` via the chained
      pre-push hook — expect "Pushing to Dolt remote..." ahead of git's output.

## Deferred, not silently dropped
- [ ] 6.1 File a bead for design.md's open question: whether `HOOK`'s `exit 0`
      "shelf not cloned → do not block" fail-open deserves the same scrutiny. Do not
      resolve it inside this change.
