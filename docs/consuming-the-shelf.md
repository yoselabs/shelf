# Consuming the shelf — how a project onboards

The **canonical consumer setup**. Onboarding any project into the micro-software approach is three
steps. The full agent behaviour lives in one place — [`agent-loop.md`](agent-loop.md) — and matures
there; the steps below just wire a project to it.

## 1. Depend on the shelf (git + tag — distributable, never a local path)

```toml
# <project>/pyproject.toml  →  [tool.uv.sources]
anyllm = { git = "https://github.com/yoselabs/shelf", subdirectory = "packages/anyllm", tag = "anyllm-v0.1.0" }
```

`uv.lock` pins the commit, so the project clones + builds anywhere. Never commit a local `{ path = … }`
source — it ties the project to one filesystem. (For local co-development of shelf + a consumer, use an
*uncommitted* override; see [`agent-loop.md`](agent-loop.md) §6.)

## 2. Install the commit guard (structure, not discipline)

The shelf ships a hook that **refuses to commit a local `path=`/editable shelf source** — so the
co-development override can never leak into a commit and break CI or another checkout. Install it once.

**Pre-commit framework** — add to `.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/yoselabs/shelf
  rev: <a shelf commit or tag>
  hooks:
    - id: no-local-shelf-source
```

**Native git hook** (no pre-commit framework) — point at the shelf clone's script:

```bash
printf '#!/bin/sh\nexec python3 "$SHELF_HOME/tools/hooks/forbid-local-shelf-source.py"\n' \
  > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

## 3. Paste this resolver block into the project's `AGENTS.md` / `CLAUDE.md`

This is the only thing duplicated per repo — tiny and stable. It reaches the full loop from the local
shelf clone (which every contributor has anyway), touching GitHub only on greenfield or a real
adopt/promote — never just to start a session.

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
