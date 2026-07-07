# 0001 — Repo topology: one shared repo, git-tag versions, apps consume across the boundary

- **Status:** decided (2026-07-07)
- **Expires:** 2027-01-07 (re-justify at the half-year)
- **Track:** topology

## Decision

One shared repo (`shelf`) houses the software as an **internal uv workspace** (packages edited
atomically). Versions are **namespaced git tags** (`anyllm-v0.2.0`) — no PyPI, no publish step beyond
`git push --tags`. Separate app repos consume across the boundary:

```toml
[tool.uv.sources]
anyllm = { git = ".../shelf", subdirectory = "packages/anyllm", tag = "anyllm-v0.2.0" }
```

`uv.lock` pins the commit → reproducible.

## Hard rules

- **Tags are non-negotiable.** A bare `{ git = ... }` silently tracks HEAD — the real footgun.
- **Never delete an old tag.** Old consumers stay pinned → evolution is opt-in → no silent break.
- **Do not absorb the apps** into the monorepo — that forces one resolved version across all apps
  forever, killing the v1-here / v2-there case that git-ref pinning handles for free.
- **a2kay is just another consumer** — not a host, not a workspace member.

## Not distributed — central-and-constrained

This does NOT reopen R154's distributed-vs-central grave. R154 warned against a *public, multi-party*
registry (discovery downstream of trade between strangers). A single shared repo at N=1 has no
strangers and no publication incentive, so that failure mode is structurally absent. Central-and-
constrained is the smaller, correct instrument here; R154's doctrine is unchanged.

## Known-open

The local side-by-side dev-loop ergonomics (path source when both repos are checked out; flip to
git-tag for commit/CI) is the one thing still to smoke-test. At bootstrap, a2kay consumes shelf via a
**local path source** (`{ path = "../shelf/packages/…", editable = true }`); the git-tag form is the
production shape once shelf is pushed to GitHub and tags are cut.
