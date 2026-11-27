# Design: gate kit

## Inventory of scripts (read 2026-11-19)

| file | lines | generic? | goes to |
|---|---|---|---|
| `tools/changed.py` (= `recipes/changed.py`) | 99 | yes | core: changed files per linter scope |
| `tools/gate_state.py` (= `recipes/gate_state.py`) | 250 | yes | core: replaced by receipts and the lock |
| `tools/affected.py` | 238 | selection is stack-specific | Python adapter (graph, export fingerprint); the pass cache becomes core receipts |
| `tools/preset_drift.py` | 228 | yes (config drift, justfile recipe set) | core drift check plus rendered-justfile compare |
| `tools/hooks/forbid-local-shelf-source.py` | small | shelf rule consumers inherit | package, called by a hook entry that needs no clone |
| `tools/size_caps/size_caps.py` | 79 | shelf repo rule (caps 400/80/800) | stays; declared as an extra step |
| `tools/arch_rules/arch_rules.py` | 214 | shelf repo rule | stays; extra step |
| `tools/catalog/catalog.py` | 144 | shelf ontology projection | stays |
| `tools/blueprint_fitness/blueprint_fitness.py` | 171 | blueprint's own pytest plugin | stays in the blueprint package |
| `recipes/check_coverage.py` | 35 | stack: python | Python adapter |
| `recipes/check_dockerfile_pins.py` | 136 | stack: dockerfile | its stack adapter |
| `recipes/check_godot.py`, `unity_integrity.py` | 140, 83 | framework | framework profiles |

## Proposed package split

```
any-gate            neutral core: steps, budgets, timing, receipts, run guard, lock/slots, changed files, reach report, drift, secret-scan call
any-gate-python     adapter: workspace graph, uv export fingerprint, pytest runner, import-linter/ruff arch role
any-gate-<stack>    one adapter per added stack (dotnet, node, ...)
blueprint           audit and contracts; CLI dispatches to the above; renders the justfile
```

The core never imports an adapter or a consumer (the shelf's one invariant, enforced by the import-linter contract). Adapters register
through a small entry-point or explicit registry that blueprint reads from the declared stacks.

## Moon versus own

| | moon | own core plus adapters |
|---|---|---|
| ADR 0021 trials | correct and fast warm (5-7 s), but 53 generated `moon.yml` plus our generator; two defaults serve stale passes; Python toolchain infers 3 of 6 edges, rewrites `uv.lock` | the measured replay: median 1.5 package suites per commit using `uv export` per package |
| per-package fingerprint from `uv export` | not available; `cacheStrategy: hash` on task deps | native |
| second language | native task graph | needs one adapter per stack |
| code to own | a generator and moon config | the core (a few hundred lines extracted from existing scripts) plus adapters |

**Decided (owner, 2026-11-19): own core.** ADR 0021 is rewritten to record it and the revisit trigger (adapter cost, not language count).

Implication of the owner's note that blueprint may later be rewritten in Rust: everything the core persists or exposes is language-neutral
(CLI verbs, declarative config in `blueprint.toml`, receipts and rendered files as documented plain text such as JSON). No pickles, no
Python-only plugin objects across the boundary; adapters are described by capabilities, so a Rust core could call a Python adapter as a
subprocess. For now the implementation is Python.

## Extraction from task-loop, concretely

| piece | source | note |
|---|---|---|
| run guard | `dev/runtests.py` in worktree `.worktrees/loop-f2943fed` at 5a940722b (removed from task-loop `main` by 9e965b00b) | rewrite for pytest, test first; shelf's `stream-proc` may already cover the process-tree kill |
| receipt key and ledger | `dev/affected.py` ledger and gate-host design | key over closure fingerprints, not per-test bytes (D3 of `gate-test-loop`) |
| coupling rules for conftest and data dirs | `dev/rule_inputs.py` history | match unique paths, never basenames |
| `reach` report | `dev/reach.py` | prints suites selected per recent commit |

## Consumer migration

| repo | state | change |
|---|---|---|
| a2kay | most converged | delete its `gate_state.py` and `SHELF_HOME` hook entries, adopt the rendered justfile, flat gate to selected tests, coverage via pytest (the duckdb issue behind its coverage.py wrapper needs a documented answer first), keep `slow` and fake models |
| task-loop | own selector and ledger; stale audit | adopt the package, delete its copies, re-run its audit; it also vendors shelf packages into a skill, so the new package arrives the same way |
| OGY | no gate or hooks | first adoption through `blueprint` |
| shelf | reference | consumes its own packages by workspace edge, as for any package |

## Risks

- The core must stay language-neutral; the second adapter is the test of that. Write its interface against `dotnet.toml` before coding.
- Name and split are proposals; one package versus three is decided after the extraction shows how coupled receipts and the run guard are.
- Task-loop's removed code means extraction reads git history; behaviour is re-specified by tests, not copied.
