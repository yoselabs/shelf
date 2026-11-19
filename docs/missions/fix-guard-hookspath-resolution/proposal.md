## Why

`tools/hooks/install.py` writes the commit guard to `<git-dir>/hooks/pre-commit` — a
hardcoded path (line 52: `hooks = git_dir / "hooks"`). It never consults
`git config core.hooksPath`. When a repo sets that, **git stops reading `.git/hooks`
entirely**, so the installer reports success, the file exists on disk, `ls .git/hooks/`
shows it, and the guard never runs again.

**Verified on this repo, 2026-08-12, not inferred.** Adopting beads set
`core.hooksPath = .beads/hooks`. A probe hook written to `.git/hooks/pre-commit`
containing `exit 1` did **not** block a commit — the commit succeeded cleanly. shelf's
own clone was, at that moment, running unguarded while every visible signal said
otherwise. Recorded as bead `shelf-efh`.

**This is not a beads problem.** `husky`, `lefthook`, and the `pre-commit` framework all
set `core.hooksPath` the same way. Any consumer using any of them has a dead guard today
and no way to notice.

The failure mode is what makes this worth fixing properly rather than patching the path.
`docs/consuming-the-shelf.md` §2 calls the guard "required per clone" and instructs
onboarding to trust the installer's `✔` — but that checkmark attests that a *file was
written*, not that a *hook will fire*. Those came apart, and nothing in the system could
tell. The guard's whole job is to make a class of mistake impossible; a guard that fails
open while claiming success is worse than no guard, because it is *believed*.

This also unblocks `shelf-gag` (guard enforcement is per-clone), which is currently
`blocked` behind this bead: folding a working-tree check into `make check` is pointless
while an installed hook can't fire.

## What Changes

1. **Resolve the hook directory correctly.** Replace `git_dir / "hooks"` with
   `git rev-parse --git-path hooks`, which honors `core.hooksPath` natively and falls
   back to `.git/hooks` when it is unset. Verified against both cases: returns
   `/…/.beads/hooks` here, `.git/hooks` in a fresh repo. Available since git 2.5.
   The existing relative→absolute normalization stays — `--git-path` returns a relative
   path when the target is relative.

2. **Prove the hook actually fires; don't infer it from a successful write.** Add a
   verification step that runs after install and, on success, changes the installer's
   claim from "installed" to "verified live". It seeds a throwaway offending state,
   invokes the resolved hook the way git would, and asserts it exits non-zero — the
   direct analogue of the probe that found this bug. If verification fails, the
   installer exits non-zero and says so; a guard that cannot be proven live is reported
   as absent.

3. **Make the foreign-hook refusal accurate and actionable.** The current message
   assumes the obstacle is a hand-written hook. Now it is usually a *tool-managed* one.
   Detect the common managers by their own markers (beads' `BEGIN BEADS INTEGRATION`,
   husky, lefthook, pre-commit framework) and name the manager plus its correct
   extension point, instead of telling the operator to hand-edit a file that its owner
   will regenerate. For beads specifically, the right answer is appending **outside**
   the managed markers — the pattern `docs/runbooks/adopt-beads.md` §2.2 already
   documents for `bd dolt push`.

4. **Record the inversion the runbook found.** When `core.hooksPath` points *inside* the
   working tree (beads' `.beads/hooks`, which `bd init` commits), hooks become tracked
   files that travel with a clone. That contradicts the "git hooks are per-clone and
   cannot be committed" premise `consuming-the-shelf.md` §2 is built on. Document it
   where the premise is stated; it is the seam `shelf-gag` will build on.

## Non-goals

- **Automatically chaining the guard into a foreign hook.** Tempting and wrong for now:
  each manager owns its file and regenerates it on its own schedule, so a silent
  append is a future silent breakage — the exact failure class this change exists to
  end. Diagnose precisely, let the operator place it. Revisit if a real consumer hits
  the refusal often enough to be a burden (a trigger, not a plan).
- **Folding guard-liveness into `make check`.** That is `shelf-gag`, and it should be
  proposed on its own once this lands and its blocker clears.
- **Migrating shelf or any consumer off beads' `core.hooksPath` mode.** Not broken —
  just undocumented, now documented.
- **A shelf package.** This is repo tooling. Two hook-path lookups and a diagnostic do
  not earn a promoted package (constitution: protection is earned).

## Impact

- `tools/hooks/install.py` — path resolution, verification step, refusal diagnostics.
- `docs/consuming-the-shelf.md` §2 — the `✔` now means verified-live; note the
  tracked-hooks inversion.
- `docs/runbooks/adopt-beads.md` — cross-reference from the `core.hooksPath` section.
- Closes `shelf-efh`; unblocks `shelf-gag`.
- **Existing consumer clones stay silently unguarded until they re-run the installer.**
  No change can repair a hook from inside this repo. Re-running is the only remedy, so
  it needs saying explicitly wherever consumers are told to onboard — otherwise this
  fix protects new clones and quietly abandons current ones.
