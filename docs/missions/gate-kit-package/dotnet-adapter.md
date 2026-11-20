# The .NET adapter, written against `dotnet.toml` (task 11)

Purpose: test that the core is not Python-shaped by listing what a second adapter must supply, before writing one. Read 2026-11-20 against
`packages/blueprint/src/blueprint/profiles/dotnet.toml` (roles toolchain, formatter, linter, types, dependencies, tests, coverage, spelling,
architecture) and the `any-gate` source.

## What an adapter supplies

| capability | Python adapter today | .NET adapter would be |
|---|---|---|
| units | `packages/*` members of the uv workspace | test projects (`*.csproj` with a test SDK) |
| edges | `[project] dependencies`, optional dependencies, dependency groups | `<ProjectReference>`, `Directory.Build.props` imports |
| third-party set per unit | `uv export --package X` hash | the unit's `packages.lock.json` (committed, `RestorePackagesWithLockFile`), hashed; central versions in `Directory.Packages.props` |
| what a root change means | `[tool.pytest]` and `[tool.coverage]` reach every suite, the rest none | `Directory.Build.props`, `.editorconfig`, `global.json`, `Directory.Packages.props` reach every unit |
| plugins that load into every run | `pytest11` entry points | MSBuild props or analyzers referenced from `Directory.Build.props` (same rule: touched ⇒ all) |
| no-effect paths and always-run repo tests | `[tool.any-gate.python]` | the same keys under `[tool.any-gate.dotnet]` |
| a unit's fingerprint | its files, its dependencies' files and locks, root inputs | the same recipe over `bin/` and `obj/`-excluded trees |
| the runner | pytest in stages | `dotnet test` per project (MTP or VSTest), a wall and idle limit |

## What the core is, measured

| core piece | neutral? | evidence |
|---|---|---|
| receipts, plan line `unit<TAB>key`, `GateState`, `start`, `passed`, `pre-push` | ✅ | a unit is an opaque string; keys are hashes; nothing reads a language |
| `steps`, `changed` (fnmatch globs), lease | ✅ | commands and globs only |
| the run guard (wall and idle limits, process-tree stop) | ✅ | `stream-proc`, takes any command |
| `any_gate test` and `run.py` (before task 13) | ❌ | runs `python -m pytest`, loads `any_gate.lanes_plugin`, sizes xdist `-n` workers, takes `-- PYTEST_ARGS` |
| `workers()` sizing | ⚠️ | the formula (cores, RAM, test count) is neutral; its only caller is the pytest stage |

## Finding and the change it asked for (done: task 13)

The core is Python-shaped in exactly one place: the `test` verb carries the pytest runner. Everything a .NET adapter needs from the core
(receipts, plan, lease, limits, state, steps, changed) is already neutral.

Change (done after this note, `shelf-3pcn.7`): the `test` verb takes the runner as a command template per unit, so the core runs
`<runner> <unit>` under the lease and limits and records the receipt, and the pytest staging (`run.py`, `lanes_plugin.py`, `--workers`) moves
into `any-gate-python` as one runner. A `dotnet test` runner is then a few lines in `any-gate-dotnet`. The lane idea (serial, quarantine) is
a runner feature, not a core one: the .NET equivalent is a trait filter.

## Not covered

No .NET code exists, so nothing here is run. lifesim is the only .NET consumer and its test layout (Godot project beside a solution) is
unread for this note.
