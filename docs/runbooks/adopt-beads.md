# Runbook — adopt bd (beads) as a repo's work queue

**Not a package.** Beads (`bd`, [github.com/gastownhall/beads](https://github.com/gastownhall/beads))
is a distributed issue tracker built on Dolt. This is an operational pattern for any repo that adopts
it — bootstrap once, then keep it wired — so the next consumer doesn't re-derive the same gaps
(a2web hit three of them adopting it, 2026-08-05/06: the status-mapping mismatch below, a personal-
identifier scan that would have silently narrowed, and the git-sync gap in Phase 2).

**Beads is part of onboarding a shelf consumer, opt-out by default.** The `onboard-consumer` skill
(`<shelf>/.agents/skills/onboard-consumer/SKILL.md`) runs the `beads` operation
(`tools/onboard/beads.py`) automatically unless `--no-beads` is passed — `bd init`, config set with
readback (never trust the success message, see §1.2 below), and the `bd dolt push` chain (§2.2)
appended after bd's own markers, all in one idempotent pass, and refusing to run before the commit
guard has verified (§1.2's ordering landmine). This runbook is now that operation's justification:
every finding below is *why* the operation asserts what it asserts, kept here rather than folded
silently into the code so the next person hitting a bd surprise can see it was already found once.

---

## Phase 1 — Bootstrap (one-time, per repo)

### 1.1 Prerequisites

- `bd` installed (`brew install beads` or per `github.com/gastownhall/beads`'s own instructions).
- A git remote the repo already pushes to — `bd` piggybacks its own ref namespace on it, no
  separate service to stand up.
- Decide **embedded vs server mode** before running `bd init`. Embedded (default) serves one writer
  at a time — correct for a mostly-sequential-agent or small-team repo. Server mode
  (`dolt sql-server`) is the upgrade path if genuine concurrent-write conflicts actually appear;
  don't reach for it speculatively.

### 1.2 Initialize

```sh
bd init --non-interactive --role maintainer
```

Not `--team` or `--contributor` — both are interactive-only wizards and reject
`--non-interactive` outright. This one commit touches only new files (`.beads/`, `AGENTS.md`,
`.claude/settings.json`, `.agents/skills/beads/`, `.codex/`) plus an **additive**, marker-delimited
block appended to an existing `CLAUDE.md` if one exists — verify that with `git show HEAD --stat`
and `git diff HEAD~1 -- CLAUDE.md` before trusting it blindly on a repo you haven't tested this on.

**If `CLAUDE.md` is a symlink to `AGENTS.md`, `bd init` handles it correctly but leaves a wart.**
Verified on shelf (2026-08-12), whose `CLAUDE.md` is a symlink: `bd init` detects the symlink,
prints `Warning: CLAUDE.md is a symlink to AGENTS.md; skipping managed section injection to
preserve link mode/content`, and does not follow or clobber it. Good. But its *Codex* installer
writes to `AGENTS.md` unconditionally, and the Claude integration block lands there too — so the
target file ends up with **two near-duplicate `## Beads Issue Tracker` sections**, one per managed
marker pair (`BEADS INTEGRATION` and `BEADS CODEX SETUP`). Both are bd-managed; don't hand-merge
them (a future `bd` upgrade rewrites both). Just know the duplication is bd's doing, not drift, and
say so in your own section so the next reader doesn't try to "fix" it.

Then enable synchronous export so `.beads/issues.jsonl` never goes stale between writes:

```sh
bd config set export.auto true
bd config set export.git-add true
```

Verify empirically, don't assume: `bd create "..." ; ls -la .beads/issues.jsonl` — check whether the
file appears/updates immediately or only at commit time. **Both behaviors have now been observed:**
a2web (2026-08-06) found export happened synchronously on write, not hook-batched. homelab
(2026-08-12, same `bd` 1.1.2) found the opposite: `.beads/issues.jsonl` did not appear after several
plain `bd create`/`bd update` calls, only after `bd hooks run pre-commit` actually ran (the export
call lives inside `.beads/hooks/pre-commit`, chained into the repo's real pre-commit hook) — i.e.
export is git-commit-triggered here, which lines up with `export.git-add` existing as a setting at
all (staging a file into git only makes sense at commit time). Don't assume either behavior; the
two data points suggest it may depend on install/config details neither adoption pinned down. Test
it for real on your own repo before relying on it: `bd create "..."; ls -la .beads/issues.jsonl`
(synchronous?) then, if empty, `bd hooks run pre-commit` and re-check (commit-triggered?).

**A third adoption (shelf, 2026-08-12, `bd` 1.1.2) probably resolves the contradiction — and the
cause is a trap worth knowing on its own. `bd config set` writes to `.beads/config.yaml`, which
`bd init` **commits**.** It is a *tracked* file, so any ordinary git operation that restores tracked
state — `git reset --hard`, `git checkout -- .`, `git stash` — silently reverts your `bd config set`
calls, with no warning from `bd` and no sign in `bd`'s own output. shelf hit exactly this: the two
`bd config set` calls succeeded and printed `Set export.auto = true (in config.yaml)`, an unrelated
`git reset --hard HEAD~1` (cleaning up a scratch commit) reverted them, and 13 `bd create` calls
later `.beads/issues.jsonl` did not exist — *looking exactly like the "export is commit-triggered"
hypothesis*. `bd config get export.auto` returned `false`. Re-setting it and repeating the test gave
a **synchronous** export, immediately on the next write, matching a2web. So the likely reading of
all three data points is: **export is synchronous; a repo that observes otherwise probably has
`export.auto` not actually in effect.**

Two rules follow, and the second is the general one:

- **Never trust `bd config set`'s success message — confirm with `bd config get <key>`.** The
  message reports the intent to write, not the surviving state.
- **Re-check `bd config get` after any git operation that rewinds the working tree.** Config that
  lives in a tracked file is config that git can revert underneath you.

**`bd create` has no `--status` flag (verified on 1.1.2).** You cannot create an issue directly as
`deferred` in one call. The working sequence is `bd create "title" ...` followed by `bd defer <id>
--reason "..."` (or `bd update <id> --status <value>` for any other status). `--spec-id` IS
available on both `bd create` and `bd update` on this version; `--set-metadata` is `bd update`-only
(not accepted by `bd create`) — set it in a follow-up call, same as `--spec-id` if you're setting it
post-creation. Re-verify per your version (`bd create --help` / `bd update --help`) rather than
trusting flag availability across versions.

**Don't hand-roll a `.gitignore` for the Dolt internals — `bd init` already ships one.** It writes
`.beads/.gitignore`, which excludes `embeddeddolt/`, `backup/`, lock files, and other runtime state
on its own; only small text-ish files (`issues.jsonl`, `interactions.jsonl`, `config.yaml`,
`metadata.json`, hooks, README) end up tracked by default. Confirmed against a real adoption
(a2web): total tracked `.beads/` content was ~180KB, not the ~11MB the embedded Dolt database
actually occupies on disk. Don't add your own top-level `.gitignore` rules for this preemptively;
verify with `git ls-files .beads/` after `bd init` instead, and only add rules if something
unexpected shows up tracked.

**If the repo runs `yamllint` (or any YAML formatter/linter) in pre-commit, `.beads/config.yaml`
can fail it.** `bd init` writes that file with its own indentation conventions, not the consuming
repo's house style; a strict `yamllint` config (e.g. 2-space indentation enforced) can reject it on
the very first commit that touches it. Fix by adding `.beads/config.yaml` to the linter's ignore
list, not by hand-reformatting a file `bd` itself will rewrite on the next `bd config set`.

**Same pattern for `shellcheck`: `.beads/hooks/*` are bd-generated shell shims, not scripts you
wrote.** Verified on homelab: `.beads/hooks/pre-commit` fails `shellcheck` (SC2016, a single-quote-
vs-double-quote info-level warning inside bd's own template) the moment `shellcheck` runs
repo-wide rather than staged-files-only (`make lint` vs the pre-commit hook's normal staged-diff
scope). Fix the same way: exclude `.beads/hooks/` from the linter's config, don't hand-edit
bd-owned shell content. General lesson for adopting any linter-in-pre-commit repo: run the FULL
repo-wide lint (not just a staged-files check) once after `bd init`, not only after the specific
files you touched, since bd writes files across several conventionally-linted extensions (`.yaml`,
`.sh`/shim shell scripts, `.md`) that a staged-diff-scoped check may not exercise the same way a
full run does.

**Check `bd init`'s injected CLAUDE.md/AGENTS.md block against the consuming repo's own content
gates before trusting the commit is clean.** If the repo runs any lint/pre-commit rule over the
files `bd init` touches (a house-style rule banning certain punctuation, a line-length limit, a
required-heading check), the auto-generated text is not guaranteed to satisfy it — it's generic
boilerplate, not written for your repo's conventions. Diff the injected block and run the repo's
own gate against it before committing (same spirit as 1.2's "verify empirically, don't assume").

### 1.3 Decide the status-mapping convention up front

`bd`'s status enum has more shape than "todo/doing/done," and conflating them is the single most
common setup mistake. Three **distinct** "not ready" mechanisms, not one:

| Situation | Mechanism | Why it's distinct |
|---|---|---|
| Waiting on another tracked issue closing | a real `blocks` dependency (`bd dep add <id> <blocker> --type blocks`) | Auto-clears when the blocker closes; excluded from `bd ready`; surfaced by `bd blocked`. The dependency-blocked issue's own `status` stays `open` — this is a derived flag, not a status write. |
| Deliberately shelved, nothing specific blocking it | native `deferred` status (`bd defer <id> --reason "..."`) | The reason auto-appends to notes. |
| Waiting on something with no bead of its own (external access, a pending human decision) | manual `--status blocked` + a comment stating why | `bd blocked` does **not** surface this — that command is for dependency-derived blocks only. Use `bd list --status blocked` to find these. |

**Never invent a synthetic blocking issue just to represent "not started yet, nothing specific
blocking it"** — that case is `deferred`, not a fake dependency.

Other conventions worth locking in now rather than improvising per-issue later:

- **Linking a bead to a spec/proposal/RFC document:** `bd update <id> --spec-id "<path>"` — a native
  field, not free text. Confirmed round-trips in `bd show --json`.
- **Branch/commit provenance** (no dedicated field exists): `bd update <id> --set-metadata
  branch=<name> --set-metadata commit=<sha>`, as a documented team convention, not a `bd` feature.
- **Supersession**: `bd dep add <new> <old> --type supersedes`, not deleting the superseded issue.

### 1.4 Migrating an existing backlog file (BACKLOG.md, TODO.md, a wiki page, etc.)

If a flat-file queue already exists, don't dump it into beads verbatim — classify first:

1. **Walk every heading-level block** (or whatever the file's own unit is) and tag each as one of:
   - **issue** — has or implies a status/completion criterion → becomes a bead.
   - **narrative** — a retrospective, retraction, measurement writeup, dependency-graph essay: no
     lifecycle → **no bead.** Move it to wherever the repo already keeps findings/history (a
     `docs/findings/`-style directory, or the project's own changelog) — forcing narrative into a
     bead misrepresents it as actionable work.
   - **plan-over-issues** — a block that sequences/groups other entries (a roadmap table, a
     dependency-order note) → usually narrative too, unless it's itself trackable.
2. **Archive the source file verbatim before deleting it** — copy it into the findings/history
   location first, so every migrated bead can point at a stable anchor instead of absorbing the
   full original prose, and so migration completeness can be verified content-addressed
   (every original block resolves to either a bead or a findings-doc pointer) rather than by a raw
   count (headings are not a uniform unit — some are single issues, some are essays, some contain
   several sub-issues at a lower heading level).
3. **Bead body: short-pointer vs full-inline is a real per-repo decision, not a fixed rule.** The
   default above (short description + a pointer to an archived findings doc) is right when the
   source file mixes true narrative (retrospectives, essays) with issues, or when the migrated
   volume is large enough that bead-browsing tools should stay skimmable. But when every block is
   already issue-shaped (a homelab-style backlog: Problem + evidence + Shape-of-a-fix + Trigger,
   no pure-narrative blocks) and the goal is a full replacement rather than a queue-plus-archive
   split, there's no length constraint forcing a cut — `bd`'s description/notes fields hold
   arbitrarily long text. A second real adoption (homelab, 2026-08-12, 65 items) deliberately chose
   **full-inline, no trimming**: the source format already earned its length (dates, entity ids,
   ADR references), and cutting it for brevity alone would have thrown away exactly the evidence
   that makes an item useful months later. `bd list` stays skimmable regardless of body length
   (it shows titles, not bodies); the cost only shows up in `bd show <id>`, exactly where detail is
   wanted. Choose deliberately: pointer-to-archive when the file mixes narrative-and-issue content
   or volume argues for it, full-inline when every block is already issue-shaped and completeness
   matters more than bead brevity. Whichever is chosen, verify migration completeness by the
   matching method — content-addressed pointer-checking for the archive approach, a heading-count
   reconciliation plus sampled content-diff (expect reformatting only, no dropped paragraphs) for
   full-inline.
4. **Delete the old flat file as its own commit**, separate from the migration commit — one
   `git revert` restores it if the migration needs to be undone.
5. **Rewrite live citations.** Grep the repo for the old file's name (config comments, code
   comments, other docs) and rewrite each to cite the equivalent bead ID. Accept this as a modest,
   real readability regression — a phrase is greppable by anyone with a text editor, a bead ID needs
   `bd` installed (or the committed `.beads/issues.jsonl`, see 1.5) to resolve to its title. Expect
   this list to be longer than a first grep on the primary file suggests — homelab's version turned
   up citations in READMEs, ADRs, a `.sops.yaml` comment, and informal "backlogged" mentions in
   unrelated docs, not just the obvious config/code references. **Exclude archived change-history
   docs** (an `openspec/changes/archive/**`-style directory, a closed-PR description, an old
   changelog entry) from the rewrite — those are a point-in-time record of what was true when
   written, not a live reference, and rewriting them to point at a bead that didn't exist yet
   falsifies the history.

### 1.5 Decide whether to commit `.beads/issues.jsonl`

`bd export`'s output is gitignored by default. Commit it (`export.auto`/`export.git-add`, set in
1.2) if the repo has — or after migration, will have — comments/config that cite an issue by ID
where a reader without `bd` installed needs to resolve what that ID means (a plaintext, greppable
fallback). Skip it if nothing outside `bd` itself ever needs to resolve an ID.

If you commit it: **any personal-identifier / secret-scanning guard the repo already runs must be
widened to cover `.jsonl`.** This is a real, not hypothetical, gap — a2web's own scanner's suffix
allowlist omitted `.jsonl`, which would have let migrated backlog prose carrying a denylisted
string (an operator IP, in that case) move from a scanned `.md` file into an unscanned export while
the guard kept reading green. Verify the widened scan **red-before-green**: seed a known-bad string
into a throwaway bead, export, confirm the guard fails, then delete the throwaway bead and
re-export.

### 1.6 Document the convention in CLAUDE.md/AGENTS.md

`bd init` already injects a Beads section (Quick Reference + Rules + Session Completion protocol).
Add, as your own section (not inside `bd`'s managed markers):

- The status-mapping table from 1.3, so a future agent doesn't reinvent it per-issue.
- The `--spec-id` / `--set-metadata` conventions, if adopted.
- **State the vocabulary plainly: `backlog = kanban = beads`.** A repo that adopts `bd` usually
  already has "backlog" or "kanban" in its working vocabulary from before — without this line an
  agent (or a person) goes looking for a separate backlog file or board that doesn't exist, or
  worse, starts one. One terse line collapses the three terms to the one real mechanism.
- **An explicit override if the repo does NOT want `bd remember`/`bd prime` for persistent agent
  memory** — `bd init`'s generated block instructs agents to use `bd remember` and NOT use
  memory files, which will conflict with a repo/operator that already has a memory system. State
  the override plainly, right after the managed block, so it isn't missed.

---

## Phase 2 — Ongoing hygiene (keep it wired, catch drift)

### 2.1 Verify the git hooks are actually installed and actually do what they claim

```sh
bd hooks list
```

Expect `pre-commit`, `post-merge`, `pre-push`, `post-checkout`, `prepare-commit-msg` all
`installed`. **Installed is not the same as correct** — `bd hooks run <name>` executes the hook
body directly, letting you check what it does without waiting for a real git event to fire it.

**"Installed" can also mean "not actually connected to git" — check this before trusting the
list.** `bd init`'s default hook install mode (`--beads`) writes shims to `.beads/hooks/`, then
wires each one into the real `.git/hooks/<name>` **only if it found an existing native hook there
to chain into**. Verified on homelab (2026-08-12): the repo's pre-commit-framework hook already
existed at `.git/hooks/pre-commit`, so `bd init` correctly chained into it — but `post-merge`,
`pre-push`, `post-checkout`, and `prepare-commit-msg` had no pre-existing native hook, and `bd
init` left them as unconnected shims. `bd hooks list` reported all 5 as `installed` regardless;
`ls .git/hooks/` told the real story (only `pre-commit` present). `bd hooks run <name>` won't catch
this either, since it invokes the shim's logic directly, bypassing git entirely. **The only real
check:** `ls .git/hooks/` and confirm every hook `bd hooks list` claims is installed actually has a
file there. Fix any gap by copying the matching file from `.beads/hooks/<name>` to
`.git/hooks/<name>` and `chmod +x` it. This is a per-clone fix, git hooks are never committed
(consuming-the-shelf.md's own doctrine), so document the fix step for future clones rather than
assuming one adoption's fix travels with the repo.

**`bd init` has a SECOND hook-install mode, and it can silently disable every other hook in the
repo.** When `.git/hooks/` has no native hook to chain into, `bd init` does not leave unconnected
shims — it sets **`git config core.hooksPath = .beads/hooks`**, repointing git's entire hook lookup
at bd's directory. Verified on shelf (2026-08-12, empty `.git/hooks/`). The consequence: **git stops
reading `.git/hooks/` altogether**, so any hook another installer wrote there — or writes there
later — never runs again. Proven, not inferred: a probe hook at `.git/hooks/pre-commit` containing
`exit 1` did not block a commit; the commit succeeded cleanly. The `.beads/hooks/*` shims contain
only bd's marker-delimited block and chain through to nothing.

This is the single most dangerous thing `bd init` does, because the victim hook keeps *existing* —
its installer reports success, the file is on disk, `ls .git/hooks/` shows it, and it is dead. On
shelf it silently killed the shelf's own `no-local-shelf-source` commit guard
(`tools/hooks/install.py`, which hardcodes `<git-dir>/hooks` and never consults `core.hooksPath`).

**Check both modes after `bd init`, they are mutually exclusive:**

```sh
git config core.hooksPath          # empty => chain mode (verify per-hook, see above)
                                   # set    => hooksPath mode (.git/hooks is now dead)
```

If it's set, audit every other hook-installing tool the repo uses (`husky`, `lefthook`, the
`pre-commit` framework, any house installer) — each one that writes to `.git/hooks` is now inert,
and each one that *also* wants `core.hooksPath` will fight bd for it. Fix by chaining the other
tool's hook body into `.beads/hooks/<name>` **outside** bd's markers, the same way §2.2 chains
`bd dolt push`.

**The install mode is not stable over the repo's life — bd migrated from one to the other, on its
own, mid-session.** Observed on shelf, 2026-08-12: `bd init` put the repo in hooksPath mode
(verified — `core.hooksPath` set, `.git/hooks/` empty but for samples, and a probe hook there did
not fire). Hours later, `core.hooksPath` was **unset** and `.git/hooks/` held copies of every
`.beads/hooks/*` file. The migration copied the directory **verbatim, including a non-beads
addition chained outside the managed markers** (the §2.2 `bd dolt push` block survived byte-identical),
so nothing was lost — but the *mode you verified at init time is not the mode you will be in later*.
The trigger was not pinned down; many `bd` invocations happened in between, and any hook self-heal
could account for it. Two consequences: re-check `git config core.hooksPath` rather than trusting an
earlier reading, and do not build tooling that assumes either mode — ask
`git rev-parse --git-path hooks`, which answers correctly in both.

**One genuine upside, easy to miss:** in hooksPath mode the hooks live at `.beads/hooks/`, which
`bd init` **commits**. Hooks become tracked files that travel with a clone — inverting the usual
"git hooks are per-clone and cannot be committed" constraint that per-clone-guard runbooks
(consuming-the-shelf.md §2) are built around. Anything you chain in there is committable.

**If the repo uses the `pre-commit` framework, read this before running `bd init` — the two are
mutually exclusive, and each one's official fix silently disarms the other.** `pre-commit` does
not use `core.hooksPath`; it writes `.git/hooks/pre-commit` directly. So it and bd's hooksPath
mode compete for one slot. Verified in a scratch repo (2026-08-12):

| order | outcome |
|---|---|
| `pre-commit install` **first**, then `bd init` | bd finds a native hook and chains into it — both live. **This is the ordering you want.** |
| `bd init` first, then `pre-commit install` | pre-commit refuses: `[ERROR] Cowardly refusing to install hooks with core.hooksPath set`. Loud, recoverable. |
| `core.hooksPath` gets set after pre-commit was installed | pre-commit dies **silently** — a seeded trailing-whitespace violation committed unblocked, no warning anywhere. |

The trap is pre-commit's own hint: `git config --unset-all core.hooksPath`. Following it revives
pre-commit and **kills every beads hook**, including the `bd dolt push` chain from §2.2 — so the
beads queue quietly stops syncing to the remote while `git push` keeps succeeding. Neither tool
knows the other exists.

**So: install `pre-commit` before `bd init`, not after.** If it's already too late, don't unset
`core.hooksPath` — chain pre-commit's hook body into `.beads/hooks/pre-commit` outside bd's
markers, the same way §2.2 chains the Dolt push. And when you hit that hint in a terminal six
months from now, remember what it costs.

### 2.2 The Dolt-remote-sync gap (verified real, not hypothetical)

`bd` syncs its issue database via `bd dolt push`/`bd dolt pull` against `refs/dolt/data` — a ref
namespace **orthogonal to `refs/heads/*`**. A plain `git push` never touches it, and — verified
empirically, a2web, 2026-08-06 — `bd hooks run pre-push` (the body of bd's own installed hook)
does **not** push the Dolt ref itself. So `git push` and `bd dolt push` are two independent remote
syncs by default, and it is easy to push code, forget the queue, and leave a teammate (or another
agent, or CI) reading a stale beads state.

**Fix:** chain `bd dolt push` onto the real git `pre-push` hook, **outside** bd's own managed
markers (`.beads/hooks/pre-push`'s `--- BEGIN/END BEADS INTEGRATION ---` block — editing inside it
risks a future `bd` upgrade clobbering the addition or tripping its drift check). Append after the
`END` marker:

```sh
# <consumer> addition (not beads-managed, won't be touched by bd upgrades):
# `bd hooks run pre-push` above does NOT push the Dolt data ref
# (refs/dolt/data) — git push and bd dolt push are two separate remote syncs.
# Chain it here so a plain `git push` can never leave the beads queue behind
# on the remote. Non-fatal: a network hiccup on the Dolt push must not block
# the code push.
if command -v bd >/dev/null 2>&1; then
  bd dolt push || echo >&2 "beads: 'bd dolt push' failed — beads queue not synced to remote, push it manually"
fi
```

Non-fatal by design — a Dolt sync failure (network blip, remote auth) should warn loudly, never
block a code push unrelated to the issue queue.

**Verify it actually fires** — do not trust that appending shell to a hook file works:

1. Syntax-check: `sh -n .beads/hooks/pre-push`.
2. Seed a real local-ahead-of-remote state (`bd create "..." ...`), confirm `bd dolt push` alone
   has something to push.
3. Run the hook directly (`sh .beads/hooks/pre-push`) and confirm it reports pushing Dolt, **before**
   trusting a real `git push` to exercise it.
4. Do one real `git push` and confirm "Pushing to Dolt remote... Push complete." appears ahead of
   the normal push output. Clean up any scratch bead created for the test.

### 2.3 Close the loop at session boundaries, not just at commit time

A commit-scoped hook can't catch "an agent claimed a bead and then forgot to close or update it" —
that's a session-scoped failure, not a commit-scoped one. Two hooks, one at each end:

- **`SessionStart`** — `bd init` already installs `bd prime --hook-json`, which injects the
  close-out protocol at the start of every session. Verify it's present:
  `grep -A5 SessionStart .claude/settings.json`.
- **`Stop`** (session end) — not installed by default. Add one that warns (non-blocking) if any
  bead is still `in_progress` when the session ends:

  ```json
  {
    "hooks": {
      "Stop": [{
        "hooks": [{
          "type": "command",
          "command": "(bd list --status in_progress --json 2>/dev/null || echo '[]') | jq -c 'if length > 0 then {systemMessage: (\"⚠️  \" + (length|tostring) + \" bd issue(s) left in_progress — close or update before ending the session:\\n\" + ([.[] | \"  - \" + .id + \": \" + .title] | join(\"\\n\")))} else empty end'"
        }]
      }]
    }
  }
  ```

  Verify by pipe-testing the raw command (`echo '{}' | <cmd>`) with zero in_progress issues (expect
  empty output) and with one seeded (`bd create ...; bd update <id> --claim`) — confirm it produces
  valid JSON with a `systemMessage`, then delete the scratch bead.

### 2.4 Periodic health check

```sh
bd orphans            # broken dependency links
bd stale              # issues with no recent activity
bd list --all --json | jq -r '.[].status' | sort | uniq -c   # true status breakdown —
                       # `bd stats` under-reports: its "Blocked" count is dependency-derived
                       # only, and it doesn't surface `deferred` at all
```

`bd doctor` is **not supported in embedded mode** as of the version this was verified against
(re-check per your installed version) — don't rely on it as the health-check entrypoint.

### 2.5 What NOT to include, decided explicitly rather than by default

- **`bd remember`/`bd prime` for persistent agent memory** — `bd init`'s own injected CLAUDE.md
  block pushes this. Decide deliberately whether the repo/operator wants a fourth memory system on
  top of whatever already exists; don't let it default in silently (see 1.6).
- **Server mode** — don't adopt it speculatively; embedded mode is correct until concurrent-write
  conflicts are an observed problem, not a theoretical one.
- **Committing `.beads/issues.jsonl`** — see 1.5; only commit it if something outside `bd` actually
  needs to resolve an ID without `bd` installed.

---

## Where this applies

Any repo that adopts `bd` in embedded mode with a Dolt remote. Not shelf-owned code — this is a
setup-and-hygiene pattern to repeat per consumer, same class of knowledge as
`consuming-the-shelf.md`'s resolver block, just for a different tool. If a second consumer adopts
`bd` and hits the same gaps, that's confirmation to fold this into whatever standard
repo-bootstrap tooling exists by then — not a signal to build a shelf package around a few hook
chains and a status-mapping convention.
