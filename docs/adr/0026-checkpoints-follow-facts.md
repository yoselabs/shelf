---
id: 0026
title: checkpoints follow facts about the repo, never its size; one override format
statement: Checkpoints apply because of facts (technology, surface, trait, what happens to a file), never file counts; the agent classifies the rest; every exception is one override.
concerns: [stack, gate, workflow]
status: accepted
decided_by: owner
updated: 2026-10-12
distilled_into: pending; built under bead shelf-6q1
---

# 0026 — checkpoints follow facts about the repo, never its size; one override format

## Decision

- **Facts turn checkpoints on.** Using a technology turns on all of its checkpoints (a Dockerfile: hadolint, the
  formatter, digest pins, something builds it). What the repo is and what happens to a file add more: a CLI surface
  adds ADR 0025's `--help` checkpoints; a Dockerfile a `push: true` step builds is a shipped image (a CI smoke test,
  an updater); a compose file a deploy step applies is a deployed stack (the healthcheck and architecture policy).
  No checkpoint turns on or off by a count of files, so adding a file never flips a set of rules.
- **Detection reports facts and evidence; the agent classifies.** A fact means one thing only (`push: true` plus a
  registry login). Evidence points without proving (an `mcp` dependency: a server, or a client library), with high
  or low confidence. The agent accepts facts and high-confidence evidence, and judges low-confidence evidence itself
  or asks the owner, as it does for what nothing detects (a game, a desktop app, library versus application).
- **The classification is recorded** in `docs/blueprint/blueprint.toml` `[profile]`: kind, surfaces and traits, each
  with who decided (detected, agent, owner) and a justification the agent writes, or writes up from the owner's
  words. Rejected evidence is recorded with its reason and asked again only when the evidence changes.
- **Closed lists**: kind = library, application, infrastructure; surface = HTTP server, MCP server, CLI, web UI,
  desktop app, game; trait = deployed, ships an image, holds secrets, stores data, LLM-backed, scheduled jobs.
  A microservice is an application with a server surface and the deployed trait. The lists grow by an ADR.
- **A declaration only adds.** Declaring a surface or trait detection missed turns on its checkpoints; removing a
  checkpoint is always an override.
- **One override format.** Every exception to a blueprint checkpoint is an `[[override]]` in `blueprint.toml`: the
  checkpoint id, an optional scope (a path, a line, a compose service), the reason, who decided, and an expiry or an
  ADR. It replaces `[[ignore]]` and the in-file markers (`# lenient:`, `# strict: no -e`, `x-policy-exempt`); the
  compose policy reads the same file (`conftest --data docs/blueprint/blueprint.toml`, tried 2026-10-12). A linter's
  own suppression (`# noqa`, hadolint `ignored:`, `# shellcheck disable`) stays where the linter reads it and carries
  a reason. Every report lists every override at the top.
- **`blueprint checkpoints`** lists each checkpoint, what it checks and the fact that turns it on, so an agent knows
  what to declare or override.
- **Per-file linters run on changed files.** A detected technology's per-file linters (hadolint, dockerfmt,
  shellcheck, shfmt, compose config, nix fmt, ruff) run on the files changed against the base branch; checks that
  read across files (type checking, architecture, dependencies) run whole-repo; CI runs everything.

Why: size tiers (shell-scripts, dockerfile-lite, compose-lite, 2026-10-11/12) picked rules by counting files, so
the count said nothing about what the repo is, and crossing it flipped a set of rules at once. Exceptions had grown
five shapes in two days.

## Rejected

- Size tiers ("light" profiles for a few files): not deterministic in the way that matters, and a file count is
  not a purpose.
- Detecting everything by heuristics: an `mcp` dependency fires on the shelf's mcp-bridge client library; a wrong
  guess is worse than one question to the owner.
- Exception markers in the files they except: each needed its own parser and none was listed anywhere.

## History

- 2026-10-12: grilled with the owner (grill-with-docs) after the size tiers shipped; accepted. Replaces the tiers in
  shell-scripts.toml, dockerfile-lite.toml and compose-lite.toml; amends ADR 0025 (scripts answer `--help`, its
  `# lenient:` waiver becomes an override).
