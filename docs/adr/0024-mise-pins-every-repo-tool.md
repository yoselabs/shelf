---
id: 0024
title: mise pins every repo tool, locked
statement: Each repo pins the tools that build or test it exactly in mise.toml, locked in mise.lock; agent CLIs are never pinned, git gets a floor; uv keeps Python, global.json the .NET SDK.
concerns: [stack, gate]
status: accepted
decided_by: owner
updated: 2026-11-20
distilled_into: blueprint stack.tool-pins, stack.agent-cli-pins, stack.tools-installed (concerns/tool_pins.py); the shelf's mise.toml, mise.lock and `just tools`
---

# 0024 — mise pins every repo tool

## Decision

`mise.toml` pins uv, just, prek, bd and framework editors (Godot) at exact versions; `mise.lock` holds
per-platform checksums; `mise install --locked` is the one install command, run by a `just tools` recipe
with the user's own mise config ignored (`MISE_IGNORED_CONFIG_PATHS`: its `latest` tools would make
`--locked` refuse). mise reads `global.json` for .NET instead of a second pin, and installs no Python
(`.python-version` is uv's). Where just is the `rust-just` dev dependency (ADR 0023) mise does not pin it
again: one pin per tool. git-lfs is not pinned here: it comes from the system package manager (History, 2026-10-12). mise's tasks and env features are not used. Blueprint checks the pins without network and,
in the audit, that installed versions equal them.

Why: tools drifted across machines (bd 1.1.2 vs 1.3.1 migrated a shared database), and just is not
preinstalled outside Python repos.

Amended 2026-11-20: the pin covers what builds or tests the repo (uv, just, prek, bd, gitleaks, editors). Agent CLIs
(codex, claude code, opencode, gemini) are never pinned: they update themselves on each person's machine, so an exact
pin is false the day they do and fights macOS and NixOS installs. A machine-owned system tool (git) gets a minimum
(`git = ">=2.40"`), not an exact pin; the audit checks the installed version meets it. `stack.agent-cli-pins` flags a
pinned agent CLI (list: `blueprint/tools.toml`); as a new checkpoint it warns until the repo's next audit (ADR 0018).

## Rejected

- proto: third-party .NET plugin that cannot read global.json, hand-written plugins, unstable lockfile, trust step.
- aqua: no .NET or mono Godot without a local registry and policy; duplicates every pin.
- Native pins only: leaves just, prek, bd and the Godot editor unpinned.

## History

- 2026-10-11: proposed after the trial (`docs/research/blueprint-skill/research/toolchain-installer.md`).
- 2026-10-11: accepted by the owner; shelf-1y4.19 builds the pin checks and pins the shelf and lifesim.
- 2026-10-11: built (shelf-1y4.19): the install recipe is `just tools`, since `bootstrap` already names consumer onboarding; just stays with uv where rust-just pins it.
- 2026-10-12: git-lfs leaves mise: its shim breaks git clone in an untrusted checkout (lifesim audit).
- 2026-10-27: gitleaks leaves the pins (owner: remove gitleaks everywhere); blueprint's `secrets.scanner` checkpoint and the tool-pin rule for it are removed. The sops checks stay.
- 2026-11-20: gitleaks returns to the pins (mission blueprint-multi-stack-contracts, task 6). The 2026-10-27 removal paid for a full-history scan in the gate; the scan now covers only staged or changed code (`python -m blueprint.secret_scan staged|range|full`), and `secrets.scanner` checks the pin and that a hook or the gate runs it.
- 2026-11-20: amended (shelf-y4je, owner): agent CLIs are never pinned; machine-owned tools get a floor.
