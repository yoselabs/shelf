## Why

`docs/runbooks/adopt-beads.md` has been through three adoptions (a2web, homelab, shelf) and
grown to ~300 lines. Look at what every one of those lines is actually doing:

- "Verify empirically, don't assume — `bd create` then `ls .beads/issues.jsonl`"
- "Installed is not the same as correct — run `bd hooks run <name>`"
- "Don't trust `bd config set`'s success message — confirm with `bd config get`"
- "Check `bd init`'s injected block against the repo's own content gates"
- "Install `pre-commit` **before** `bd init`, not after"
- "Verify the widened scan red-before-green"
- "`ls .git/hooks/` and confirm every hook it claims is installed has a file there"

Every single one is either an **ordering constraint** or a **verification obligation**. Prose
can express neither. A runbook can only ask the next agent to be careful, and each adoption
has discovered a fresh way to not be careful enough — so the document grows by a paragraph
per incident and never converges. It is a list of things that will eventually be skipped.

The evidence is this repo. Adopting beads here produced four defects in one session, and each
one is a runbook rule that was followed and still failed:

| what happened | the runbook rule it defeated |
|---|---|
| `bd init` set `core.hooksPath`, silently killing the commit guard | "verify the hooks are installed" — they *were*; the other tool's weren't |
| `git reset --hard` reverted `bd config set` | "enable `export.auto`" — it was enabled, then wasn't, with no signal |
| `pre-commit` and beads contend for one hook slot | not discovered until the fourth adoption |
| guard reported `✔` while provably dead | "run the installer" — it ran, and lied |

None of these are agent carelessness. They are the predictable result of encoding ordering and
verification as prose that a human or agent re-executes by hand, every time, in whatever order
they read it.

**The fix is to stop writing instructions for an agent to follow and start prescribing a target
the repo runs.** `make bootstrap` can be idempotent; a paragraph cannot. It can encode ordering
as prerequisites; a paragraph can only mention ordering and hope. It can assert liveness and
fail; a paragraph can only ask. And it converts "the next agent must remember 14 things" into
"the next agent runs one command, and the command remembers."

## What Changes

1. **A bootstrap contract, prescribed for every repo — beads or not.** A new
   `docs/runbooks/repo-bootstrap.md` defines what `make bootstrap` must guarantee:
   **idempotent** (safe to re-run, always), **ordered** (dependencies encoded as
   prerequisites, not prose), **verifying** (asserts the effect it intended, never the
   artifact it wrote), and **honest** (three outcomes — live, not-live, could-not-check —
   never collapsed into two). This is a *contract*, not a script: repos differ, and what they
   share is the obligation, not the implementation.

2. **Content assertions move into `make check`; `make bootstrap-verify` holds environment
   assertions and is not a gate.** These are different kinds of claim and were conflated in an
   earlier draft (see D4). "No local `path=` shelf source" is a property of the repo's files —
   true on any clone, needing no hooks, no onboarding, and no CI mode. "The pre-commit hook
   actually blocks" is a property of one working copy. Today the former is enforced *only* by
   a pre-commit hook, which is precisely how this repo went unguarded unnoticed. Putting it in
   the gate makes the hook fast feedback rather than enforcement: a dead hook then costs
   latency, not safety.

3. **The beads runbook is rewritten in the prescriptive voice, and stays self-contained.**
   Not deleted, not merged into the general one — most repos here will adopt beads, and its
   reader should not have to assemble the picture from two documents. What changes is the
   voice: every "verify X" becomes "your bootstrap asserts X", every "remember to Y" becomes
   "bootstrap does Y in this position, for this reason". The hard-won *findings* stay in full
   — they are the justification for each assertion, and losing them would invite re-deriving
   them. What goes is the imperative to a human reader.

4. **The ordering discovered this session becomes a prerequisite graph, not a warning.**
   `pre-commit` before `bd init` is currently a bolded sentence that works only if read in
   time. As a Make prerequisite it cannot be got wrong.

5. **AGENTS.md points at `make bootstrap` as the entry point**, so a cold agent's first move
   on an unfamiliar clone is one command rather than a runbook walk.

## Non-goals

- **A shelf package, or a bootstrap CLI.** Resolution 0004 settled the shape for exactly this
  class of thing: the toolchain is a *config preset that consumers inherit*, not a program
  they install. A contract plus a reference `Makefile` fragment, not `shelf-bootstrap`.
- **One universal bootstrap implementation.** Repos legitimately differ (uv vs poetry, beads
  or not, pre-commit or not). The contract is what is shared. A repo satisfying it with
  fifteen lines of Make is fully compliant.
- **Auto-adopting beads anywhere.** The contract is beads-agnostic; beads is one optional
  module that plugs into it.
- **Resolving the beads/pre-commit hook-slot contention automatically.** Which tool owns
  `.git/hooks` is a repo decision (see `fix-guard-hookspath-resolution` D3). Bootstrap
  enforces the *order* that avoids the conflict, and reports it when it already exists.

## Relationship to `fix-guard-hookspath-resolution`

That change makes the guard verifiable — resolve the hook path correctly, then prove the hook
fires. This change generalizes that principle to everything bootstrap installs, and gives the
verification a standing home so it runs more than once.

They compose and should land in order: the guard fix supplies the first real
verify-by-behavior implementation; bootstrap adopts it as the pattern. Landing this one first
would mean prescribing a contract with no working instance of it, which is exactly the "do NOT
build on spec" the constitution warns about.

## Impact

- New: `docs/runbooks/repo-bootstrap.md`, `make bootstrap`, `make bootstrap-verify`.
- Rewritten in voice, preserved in substance: `docs/runbooks/adopt-beads.md`.
- `Makefile` — `bootstrap` and `bootstrap-verify` targets; `check` gains a content assertion,
  and does **not** depend on `bootstrap-verify` (D4).
- `AGENTS.md`, `docs/consuming-the-shelf.md` — onboarding becomes one command.
- `make check` gains one cheap content assertion, not a verification suite (D4).
- **`shelf-gag` is no longer downstream of this change.** It is the cheapest and highest-value
  of the three, depends on neither of the others, and has been unblocked and raised to P1. Do
  it first; this change assumes it has landed.
- **This repo has no CI** (no `.github/workflows/`), so `make check` is the only gate that
  exists — which is what makes the content/environment split decisive rather than stylistic.
