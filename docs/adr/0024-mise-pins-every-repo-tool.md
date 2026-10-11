---
id: 0024
title: mise pins every repo tool, locked
statement: Each repo pins its tools exactly in mise.toml with a committed mise.lock; `mise install --locked` installs them; uv keeps Python, global.json keeps the .NET SDK; just keeps the tasks.
concerns: [stack, gate]
status: accepted
decided_by: owner
updated: 2026-10-11
distilled_into: not yet (shelf-1y4.19)
---

# 0024 — mise pins every repo tool

## Decision

`mise.toml` pins uv, just, prek, bd and framework editors (Godot) at exact versions; `mise.lock` holds
per-platform checksums; `mise install --locked` is the one install command, run by `just bootstrap`.
mise reads `global.json` for .NET instead of a second pin, and installs no Python (`.python-version`
is uv's). mise's tasks and env features are not used. Blueprint checks the pins without network and,
in the audit, that installed versions equal them.

Why: tools drifted across machines (bd 1.1.2 vs 1.3.1 migrated a shared database), and just is not
preinstalled outside Python repos.

## Rejected

- proto: third-party .NET plugin that cannot read global.json, hand-written plugins, unstable lockfile, trust step.
- aqua: no .NET or mono Godot without a local registry and policy; duplicates every pin.
- Native pins only: leaves just, prek, bd and the Godot editor unpinned.

## History

- 2026-10-11: proposed after the trial (`openspec/changes/blueprint-skill/research/toolchain-installer.md`).
- 2026-10-11: accepted by the owner; shelf-1y4.19 builds the pin checks and pins the shelf and lifesim.
