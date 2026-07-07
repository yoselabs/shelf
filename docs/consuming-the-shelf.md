# Consuming the shelf — how a project onboards

This is the **canonical consumer directive**. Onboarding any project into the micro-software approach
is two steps:

## 1. Depend on the shelf (git + tag — distributable, never a local path)

```toml
# <project>/pyproject.toml  →  [tool.uv.sources]
anyllm = { git = "https://github.com/yoselabs/shelf", subdirectory = "packages/anyllm", tag = "anyllm-v0.1.0" }
```

`uv.lock` pins the commit, so the project clones + builds anywhere. Never commit a local `{ path = … }`
source — that ties the project to one filesystem. (For local co-development of shelf + a consumer, use
an *uncommitted* path override.)

## 2. Paste this block into the project's `AGENTS.md` / `CLAUDE.md`

> ### The shelf — shared micro-software you consume
>
> This project consumes **the shelf** (`github.com/yoselabs/shelf`) — the shared home of small, ownable,
> contract-guaranteed software pieces, pinned here by git tag. Read its `AGENTS.md` + `constitution.md`
> before contributing.
>
> - **Reach for the shelf first.** Before hand-rolling a helper, wrapper, or any substrate glue, check the
>   shelf (its `glossary.md` + `packages/`). If a piece already covers the need, depend on it (git+tag)
>   and write less code.
> - **Adopt only if it WINS.** Take a shelf piece only when it is DEEP (hides real complexity), STABLE
>   (settled API), and lighter than what you'd write. Otherwise duplicate locally — duplication beats the
>   wrong abstraction. Never adopt a shallow or churning piece just to reuse.
> - **Contribute back.** When you write substrate this project no longer wants to care about — and a
>   second consumer would want it — promote it to the shelf (promotion-not-publication: it graduates when
>   a 2nd consumer pulls it). Improving a shelf piece improves every consumer.
> - **Consider it every time** you create something new or fix a quirk: is this the product, or substrate
>   the shelf should own? Prefer small, ownable pieces. Make micro-software.

The guardrail (DEEP · STABLE · WINS) is deliberate: it keeps "reach for the shelf" from degrading into
"add a dependency for everything." Reuse is encouraged; the wrong abstraction is not.
