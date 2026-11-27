# Consuming the shelf — what a consumer is

The **canonical description** of what it means for a project to consume the shelf: a git+tag
dependency, a commit guard, a resolver block that reaches the full loop, and (for python+uv
projects) the linter reference. The full agent behaviour lives in one place —
[`agent-loop.md`](agent-loop.md) — and matures there; what follows explains each piece and why it
exists.

**To onboard a project, run `uv run blueprint init`** in its root (a dev dependency pinned by git tag; no shelf clone). It detects the
stack, audits, then writes only what is missing: the justfile parts, the linter preset tables, the
stack's recipe files, and the hook config with `prek install` (`--no-hooks` skips both). It never overwrites a file you have, and ends with
the rows it could not set up. It also writes `mise.toml` (the tools the repo runs, at the versions found on PATH) and runs `mise lock`. Beads is opt-in: `init` suggests it, and
`blueprint init --beads` runs `bd init --skip-hooks` (see `runbooks/adopt-beads.md`). Not done by `init`: the shelf git+tag dependencies of §1 (it points at
the catalog) and the resolver block of §3; `blueprint check` lists what is still missing. This file stays the reference
for *what* each piece is and *why*. `docs/runbooks/onboard-a-consumer.md` covers the broader adoption sweep.

## 1. Depend on the shelf (git + tag — distributable, never a local path)

```toml
# <project>/pyproject.toml  →  [tool.uv.sources]
anyllm = { git = "https://github.com/yoselabs/shelf", subdirectory = "packages/anyllm", tag = "anyllm-v0.1.0" }
```

`uv.lock` pins the commit, so the project clones + builds anywhere. Never commit a local `{ path = … }`
source — it ties the project to one filesystem. (For local co-development of shelf + a consumer, use an
*uncommitted* override; see [`agent-loop.md`](agent-loop.md) §6.)

## 2. The commit guard — enforced by `just check`, accelerated by a hook

The shelf ships a guard that **refuses a local `path=`/editable shelf source**, so a co-development
override can never leak into a commit and break another checkout.

**Enforcement is the `guard` target in `just check`** (copied with the rest of the preset, §4). It
reads `HEAD` — committed content — so it holds on any clone, with no hooks, no onboarding, and
nothing installed. That matters because the alternative does not hold: a git hook is per-clone and
**any tool that claims `core.hooksPath` silently disables it** — beads, husky, and lefthook all do,
and the hook file keeps existing and looking installed while git never runs it. That happened in the
shelf's own repo and went unnoticed. Do not rely on a hook as the enforcement point.

Note what the gate does *not* read: your working tree. An **uncommitted** local override is the
supported co-development workflow (§1) and stays legitimate.

**The hooks are prek's** (blueprint's hook recipe, `research/hooks-and-beads.md` in the blueprint
change). `blueprint init` writes `.pre-commit-config.yaml` and runs `prek install`:

| entry | stage | what it does |
|---|---|---|
| bd's five events (`bd hooks run <event>`) | each git event | beads' own hook work; bd never installs hooks itself (`bd init --skip-hooks`) |
| `blueprint-hook` (`uv run blueprint gate hook`) | pre-commit | one process over the staged files: secret scan, the local-shelf-source guard, preset drift (when `pyproject.toml` is staged), `ruff check` and `ruff format --check` |
| `just check` | pre-push | the whole gate before code leaves the machine |

Print the recipe with `uv run blueprint recipe hooks`. A consumer recipe runs the pinned engine (`uv run blueprint ...`), never a shelf clone: `gate.recipe-calls` (ADR 0033).
Both are the same trade the guard makes: the hook is fast feedback, `just check` is the enforcement.

Idempotent. It asks git where hooks live (`git rev-parse --git-path hooks`, which honors
`core.hooksPath`) rather than assuming `.git/hooks`, then **proves the guard blocks** by running it
against a throwaway index before reporting success. Three outcomes, deliberately distinct:

| exit | meaning |
|:--:|---|
| `0` | installed **and verified live** — it refused a probe |
| `1` | refused (a foreign hook owns the slot, and the message names which tool and its extension point), or written but **not live** |
| `2` | **could not verify** — e.g. no shelf clone found, so the hook's fail-open branch is active. Never treat this as installed. |

**If your repo also uses beads, install this before `bd init`.** `bd init` chains into an existing
native hook, but claims `core.hooksPath` when it finds none — which installs the guard dead.

**Already onboarded before this existed?** Re-run it. A guard installed by the older version may be
silently dead, and nothing in your repo will tell you; only re-running checks.

**One inversion worth knowing:** where `core.hooksPath` points *inside* the working tree (beads'
`.beads/hooks`, which `bd init` commits), the hooks are **tracked files that travel with a clone** —
the "hooks are per-clone and cannot be committed" premise above has that exception.

**Using the pre-commit framework instead?** the onboarding writes `.pre-commit-config.yaml` for you (prek). The commit entry is `uv run blueprint gate hook` (guard, preset drift, secret scan, ruff, one process), from the `blueprint` dev dependency the onboarding adds, pinned by git tag. The shelf ships no hook repository.

## 3. The resolver block, in the project's `AGENTS.md`

This is the only thing duplicated per repo — tiny and stable. It reaches the full loop from the local
shelf clone (which every contributor has anyway), touching GitHub only on greenfield or a real
adopt/promote — never just to start a session.

**Paste it once, in its own region.** There is no projector any more (the `resolver-block` operation went with `tools/onboard`): the
block lives in a marker-delimited region of the target file, outside every other tool's managed region (this repo's own `AGENTS.md`
already carries two from `bd`). The text below is the block:

> ### The shelf — shared micro-software you consume
>
> This project consumes **the shelf** (`github.com/yoselabs/shelf`) — shared, ownable,
> contract-guaranteed software pieces, pinned in `pyproject.toml` by git tag. Reach for it before
> hand-rolling substrate; adopt only if **DEEP · STABLE · WINS**; contribute back by *promotion*.
>
> **Three things fire the loop**, not one: substrate glue you are about to write; a bug whose root
> cause was a *dependency's* behaviour; and — the quiet one — a dependency that worked fine and was
> merely **verbose**, where you wrote an expression and thought "why isn't this a method?". "Stop
> caring about X" includes how much you must type to use X. Promote the **thing** a domain has (a type
> the consumer holds), name it `any-<domain>`, never `<lib>-extra`.
>
> **Full behaviour = the shelf loop.** Resolve it **once per session, lazily** — the first time you
> consider adopting or promoting substrate, never at startup:
>
> 1. Find the local clone: `$SHELF_HOME` → `../shelf` → `~/Workspaces/shelf`.
> 2. If absent (greenfield), clone it once: `git clone https://github.com/yoselabs/shelf ~/Workspaces/shelf`.
> 3. Read `<shelf>/docs/agent-loop.md` and follow it. Load once; cache for the session.
>
> Never hit GitHub to start a session or to write code — only to clone (once) or during an actual
> adopt/promote (a lazy `git pull` at that checkpoint). Never commit a local `path=`/editable shelf
> source (the guard from §2 blocks it).

The **DEEP · STABLE · WINS** gate is deliberate: it keeps "reach for the shelf" from degrading into
"add a dependency for everything." Reuse is encouraged; the wrong abstraction is not.

## 4. Inherit the linter reference (copy, then own)

The shelf's quality bar is a **config-preset**, not a CLI ([ADR 0004](adr/0004-linters-are-a-config-preset.md)):
copy the `[tool.ruff|codespell|coverage]` blocks + the `justfile` recipes + the `dev` dependency-group
from this repo into yours, then override anything you genuinely need to. Full toolchain and the exact
copy list: **[linting.md](linting.md)**. `just check` green (whole-repo, no carve-outs) is the bar.

`blueprint init` does this copy for you (python+uv only), per table rather than overwriting: a project that already has its own
`[tool.ruff]`, `ruff.toml` or `pyrefly.toml` keeps it exactly as written. The tables come from the preset packaged in `blueprint`
(rule lists, error kinds, size caps), so no shelf clone is needed.

## 5. Pin the tools (mise)

Every tool that builds or tests the repo (uv, just, prek, bd, an engine editor) is pinned exactly in a committed `mise.toml`
and locked with per-platform checksums in `mise.lock` ([ADR 0024](adr/0024-mise-pins-every-repo-tool.md)). The preset's
`tools` recipe installs them with `mise install --locked`, leaving the user's own mise config out. After a fresh
clone run `mise trust --yes && mise install --locked` as plain commands (until the trust every mise shim refuses, uv
included), then the stack's sync and `bd bootstrap`; after a pin bump, `just tools`. `gate.clean-clone` runs the same steps. blueprint's `stack.tool-pins` checks the pins on every commit and
`stack.tools-installed` checks this machine's versions in the audit. Agent CLIs (codex, claude code, opencode, gemini) are never pinned: they update themselves per machine, and `stack.agent-cli-pins` flags a pin (the list is `blueprint/tools.toml`); a machine-owned tool such as git gets a minimum (`git = ">=2.40"`), not an exact pin. A repo that declares LFS patterns is also checked
for binaries outside LFS (`gate.lfs-binaries`) and, in the audit, for this clone's LFS filter (`gate.lfs-installed`); `gate.git-config-clean` flags a stray `core.worktree` or `core.bare` in the clone's config.
