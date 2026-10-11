---
id: 0001
title: Repo topology, one shared repo, git-tag versions
statement: One shared repo holds all packages as a uv workspace; versions are namespaced git tags, never deleted; apps stay separate repos and pin by tag.
concerns: [packaging]
status: accepted
decided_by: owner
updated: 2026-07-08
expires: 2027-01-07
distilled_into: N/A — self-enforcing via the repo layout itself (packages/, catalog/, use-cases/, ledger/ existing as directories)
---

# 0001 — Repo topology: one shared repo, git-tag versions, apps consume across the boundary

## Decision

One shared repo (`shelf`) houses the software as an **internal uv workspace** (packages edited
atomically). Versions are **namespaced git tags** (`anyllm-v0.2.0`): no PyPI, no publish step beyond
`git push --tags`. Separate app repos consume across the boundary; `uv.lock` pins the commit, so
builds are reproducible:

```toml
[tool.uv.sources]
anyllm = { git = ".../shelf", subdirectory = "packages/anyllm", tag = "anyllm-v0.2.0" }
```

Hard rules:

- **Tags are non-negotiable.** A bare `{ git = ... }` silently tracks HEAD, the real footgun.
- **Never delete an old tag.** Old consumers stay pinned, so evolution is opt-in and nothing breaks silently.
- **Do not absorb the apps** into the monorepo: that forces one resolved version across all apps
  forever and kills the v1-here / v2-there case that git-ref pinning handles for free.
- **a2kay is just another consumer**, not a host, not a workspace member.

## Why central is fine here

This does not reopen R154's distributed-vs-central grave. R154 warned against a *public, multi-party*
registry (discovery downstream of trade between strangers). A single shared repo at N=1 has no
strangers and no publication incentive, so that failure mode is structurally absent.
Central-and-constrained is the smaller, correct instrument; R154's doctrine is unchanged.

## History

- 2026-07-07: decided. Expires 2027-01-07 (re-justify at the half-year). Track: topology.
- 2026-07-08: the side-by-side dev loop was verified end to end: one shelf clone plus a per-project
  `git worktree` (`shelf-<project>`), with an editable path override kept **unstaged**. uv reads the
  working tree, the commit guard reads *staged*, so unrelated commits pass and only a staged override is
  blocked. a2kay now consumes via the production git-tag form. Mechanics: `agent-loop.md` §6;
  onboarding: `consuming-the-shelf.md`.
