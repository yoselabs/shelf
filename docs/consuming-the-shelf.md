# Consuming the shelf — what a consumer is

The **canonical description** of what it means for a project to consume the shelf: a git+tag
dependency, a commit guard, a resolver block that reaches the full loop, and (for python+uv
projects) the linter reference. The full agent behaviour lives in one place —
[`agent-loop.md`](agent-loop.md) — and matures there; what follows explains each piece and why it
exists.

**To actually onboard a project, run the `onboard-consumer` skill**
(`<shelf>/.agents/skills/onboard-consumer/SKILL.md`) rather than following §2–4 by hand — it
installs the guard, projects the resolver block, wires beads (opt-out), and copies the linter
reference in one adaptive, verified pass, and it's idempotent (safe to re-run to check a repo's
current state). This file stays the reference for *what* each piece is and *why*; the skill is the
mechanism. `docs/runbooks/onboard-a-consumer.md` covers the broader adoption sweep the skill is
part of.

**Once §4's Makefile targets are copied, `make bootstrap` is the same skill under one command**
(`make bootstrap-verify` re-checks without implying first-time setup — mechanically identical,
see `bootstrap-target-contract`'s design doc for why that's a deliberate, not lazy, choice). Before
a Makefile exists yet (greenfield, or before §4 is done), invoke the script directly:
`python3 "$SHELF_HOME/.agents/skills/onboard-consumer/scripts/onboard.py" --repo .`

## 1. Depend on the shelf (git + tag — distributable, never a local path)

```toml
# <project>/pyproject.toml  →  [tool.uv.sources]
anyllm = { git = "https://github.com/yoselabs/shelf", subdirectory = "packages/anyllm", tag = "anyllm-v0.1.0" }
```

`uv.lock` pins the commit, so the project clones + builds anywhere. Never commit a local `{ path = … }`
source — it ties the project to one filesystem. (For local co-development of shelf + a consumer, use an
*uncommitted* override; see [`agent-loop.md`](agent-loop.md) §6.)

## 2. The commit guard — enforced by `make check`, accelerated by a hook

The shelf ships a guard that **refuses a local `path=`/editable shelf source**, so a co-development
override can never leak into a commit and break CI or another checkout.

**Enforcement is the `guard` target in `make check`** (copied with the rest of the preset, §4). It
reads `HEAD` — committed content — so it holds on any clone, with no hooks, no onboarding, and
nothing installed. That matters because the alternative does not hold: a git hook is per-clone and
**any tool that claims `core.hooksPath` silently disables it** — beads, husky, and lefthook all do,
and the hook file keeps existing and looking installed while git never runs it. That happened in the
shelf's own repo and went unnoticed. Do not rely on a hook as the enforcement point.

Note what the gate does *not* read: your working tree. An **uncommitted** local override is the
supported co-development workflow (§1) and stays legitimate.

**Optionally add the hook for faster feedback** — it catches the mistake at commit time instead of
at gate time. The `onboard-consumer` skill installs it as part of onboarding (via the `guard`
operation, `tools/onboard/guard.py`); to run it standalone:

```bash
python "$SHELF_HOME/tools/hooks/install.py"   # run in the consumer repo root
```

Idempotent. It asks git where hooks live (`git rev-parse --git-path hooks`, which honors
`core.hooksPath`) rather than assuming `.git/hooks`, then **proves the hook blocks** by running it
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

**Using the pre-commit framework instead?** add to `.pre-commit-config.yaml` (skips the installer):

```yaml
- repo: https://github.com/yoselabs/shelf
  rev: <a shelf commit or tag>
  hooks:
    - id: no-local-shelf-source
```

## 3. The resolver block, in the project's `AGENTS.md` / `CLAUDE.md`

This is the only thing duplicated per repo — tiny and stable. It reaches the full loop from the local
shelf clone (which every contributor has anyway), touching GitHub only on greenfield or a real
adopt/promote — never just to start a session.

**Projected, not pasted.** `BLOCK_TEXT` in `tools/onboard/resolver_block.py` is the one source; the
`resolver-block` operation writes it into a marker-delimited region of the target file, appended
outside every other tool's managed region (this repo's own `AGENTS.md` already carries two from
`bd`), and re-projects it in place on re-run — so a consumer can be checked for drift instead of
silently carrying a stale copy-paste. The `onboard-consumer` skill runs this automatically; to
project it standalone, instantiate `ResolverBlockOperation(repo).run({})`. The text below is what
gets projected — useful to read, not to hand-copy:

> ### The shelf — shared micro-software you consume
>
> This project consumes **the shelf** (`github.com/yoselabs/shelf`) — shared, ownable,
> contract-guaranteed software pieces, pinned in `pyproject.toml` by git tag. Reach for it before
> hand-rolling substrate; adopt only if **DEEP · STABLE · WINS**; contribute back by *promotion*.
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

The shelf's quality bar is a **config-preset**, not a CLI ([resolution 0004](resolutions/0004-linters-are-a-config-preset.md)):
copy the `[tool.ruff|codespell|coverage]` blocks + the `Makefile` targets + the `dev` dependency-group
from this repo into yours, then override anything you genuinely need to. Full toolchain and the exact
copy list: **[linting.md](linting.md)**. `make check` green (whole-repo, no carve-outs) is the bar.

The `linter-preset` operation (`tools/onboard/linter_preset.py`, python+uv only) does this copy for
you, merging per-table/per-target rather than overwriting — a project that already has its own
`[tool.ruff]` keeps it exactly as written, ruff.lint included. The `onboard-consumer` skill runs it
automatically when `pyproject.toml` exists, and states plainly when it doesn't apply (non-Python
targets get the guard/resolver-block/beads pieces only).
