# Runbook — adopt bd (beads) as a repo's work queue

**Not a package.** Beads (`bd`, [github.com/gastownhall/beads](https://github.com/gastownhall/beads))
is a distributed issue tracker built on Dolt. This is an operational pattern for any repo that adopts
it — bootstrap once, then keep it wired — so the next consumer doesn't re-derive the same gaps
(a2web hit three of them adopting it, 2026-08-05/06: the status-mapping mismatch below, a personal-
identifier scan that would have silently narrowed, and the git-sync gap in Phase 2).

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

Then enable synchronous export so `.beads/issues.jsonl` never goes stale between writes:

```sh
bd config set export.auto true
bd config set export.git-add true
```

Verify empirically, don't assume: `bd create "..." ; ls -la .beads/issues.jsonl` — the file should
appear/update **immediately**, synchronously, not waiting on a git hook. (a2web's original design
assumed the export was hook-batched and needed a fix for that; it wasn't, on the version tested —
re-verify per your `bd` version rather than trusting this note indefinitely.)

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
3. **Bead body = short description + a pointer to the archived source**, not the full original
   text. A bead whose justification is longer than a short paragraph should carry a pointer to the
   archived findings doc, not the evidence itself.
4. **Delete the old flat file as its own commit**, separate from the migration commit — one
   `git revert` restores it if the migration needs to be undone.
5. **Rewrite live citations.** Grep the repo for the old file's name (config comments, code
   comments, other docs) and rewrite each to cite the equivalent bead ID. Accept this as a modest,
   real readability regression — a phrase is greppable by anyone with a text editor, a bead ID needs
   `bd` installed (or the committed `.beads/issues.jsonl`, see 1.5) to resolve to its title.

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
