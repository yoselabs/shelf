# Design: blueprint outcome contracts across several stacks

## Facts read from code (not changed yet)

- `profile.py`: `State` = declared profile + overrides + settings; `detect()` takes declared stacks else `_stack_files()` (manifests). `Profile.stacks`
  is a tuple, so a repo with several stacks already works at detection.
- `profiles/*.toml`: one file per stack, each `[[role]]` has `tool`, `install`, `config` (files that must hold), `gate` (regex that
  `just check` must reach), optional `na` or `untested`, and `[[role.alternative]]`. Every profile defines the same roles (`ROLES` in `concerns/stack.py`)
  including `architecture`.
- `concerns/stack.py` and the `stack.*` checkpoints project the roles into checkpoints; `runner.py` applies overrides and expiry.
- `recipes/`: scripts that consumers copy (`changed.py`, `gate_state.py` are byte-identical to `tools/`), plus stack-specific ones
  (`check_godot.py`, `unity_integrity.py`, `check_dockerfile_pins.py`, `check_coverage.py`).

## Decisions proposed

### D1. A role states an outcome; a stack adapter proves it

New contract per role, e.g. for `tests`: `selected-run-green-or-receipt` and `full-run-with-coverage-on-tag`. Each adapter provides the proof
(Python: reads the gate graph from `just --dump --dump-format json` and checks that the declared test step calls the shared runner, or that a
receipt exists for the closure). The `gate` regex field remains for roles that really are command shapes (a formatter was run).
The coverage role becomes tool-agnostic: any pytest-driven coverage with a floor counts (fixes shelf-2hl; coverage.py wrappers are not required).

### D2. Adapter interface (the capabilities a stack must supply)

| capability | Python (uv) | .NET | Node |
|---|---|---|---|
| units | workspace members | csproj/sln projects | package.json workspaces |
| unit graph | `pyproject.toml` deps + `uv export` | project references | workspace deps in package.json |
| fingerprint | files + export hash | files + restored package lock | files + lockfile per workspace |
| run tests | pytest | dotnet test | the repo's declared runner |
| layering | import-linter + ruff TID251 | AllowedRefs target, NsDepCop, ArchUnitNET | to research (dependency-cruiser or eslint boundaries) |
| secrets | the shared scanner | the shared scanner | the shared scanner |

Only Python is implemented in the first slice; the interface is written so the second adapter does not change the core. This is decided
by writing the .NET adapter's capabilities on paper against the existing `dotnet.toml` role text and checking nothing in the core is
Python-shaped.

### D3. Mixed repos: units declare their stack; edges across stacks are declared

Each unit folder holds one manifest; `blueprint.toml` lists `stacks` (or detection lists them). Selection runs per stack. A cross-stack edge
(a Python package that wraps a TypeScript port, a shared schema) is declared as `[[edge]] from, to, via`; an undeclared cross-stack path
selects everything (as unknown paths do today). Opinionated layout to decide (owner): one folder per unit under a common parent, one lock per
ecosystem, one root gate, cross-stack contact only through a declared contract.

Shelf itself: packages ported to another language become units with their own stack. ADR 0021's re-open trigger ("the shelf gets its first
non-Python package") is therefore real and near; `gate-kit-package` handles it. `catalog/` manifests gain a `stack` field per package (open item).

### D4. Layering is mandatory per stack

Blueprint's own registry fitness test (existing `blueprint-registry-fitness`) gains one rule: every profile has an `architecture` role that is
not `na`. New stacks (`node`, `go`, `rust`) ship their profile with it or are not supported. A stack that detection finds and that has no profile **fails blueprint** ("stack X found,
no profile"): an error, never silence and never a pass (owner, 2026-11-19). The only way past it is a justified `not-supported` override
with an expiry or an accepted ADR, as every exception is (ADR 0022).

### D5. Secret scanning

A standard open-source scanner pinned in `mise.toml` (candidate: gitleaks; task-loop's same-day revert d6e223b71 -> 739474b82 is read first
to learn why). Modes: staged files (pre-commit), `<base>..HEAD` plus working tree (gate), full tree (tag). Findings carry file and rule, never
the secret. The existing sops-sealed check is unchanged.

### D6. Hook anti-pattern checkpoints

Built as concern `hooks` (`hooks.no-tests-at-commit`, `hooks.pre-push-is-the-gate`, `hooks.fail-closed`, `hooks.no-clone-path`, `hooks.gate-always-runs`; the injection and `core.hooksPath` cases were already `gate.hooks-installed`). A post-merge gate is allowed (any-gate skips a tree that already passed; the shelf runs one on purpose), so "the gate also called by another hook" means a commit-time call only. Each reads `.pre-commit-config.yaml` and `.git/hooks`: tests in `pre-commit`; `pre-push` running anything other than the gate; the gate also
called by another hook; `core.hooksPath` not the hook manager's; a hook that always exits 0; a guard or drift script resolved through
`SHELF_HOME`, `../shelf` or `~/Workspaces/shelf` instead of a pinned dependency. Each finding names the line to delete or change.

### D7. Less churn

- Reports: written to `docs/blueprint/` only when a checkpoint's verdict set changes; the timestamp-only diff is not committed.
- Per-checkpoint input fingerprints; an unchanged checkpoint reuses its last verdict (stored like a receipt).
- Override expiry: a notice N days before it lands (setting, default proposed 14).
- Converge mode: at most one commit per shelf bump.

### D8. Rendered justfile

`blueprint render` writes the gate recipes from the declared stacks into a generated include (`import`); the repo's own recipes stay in
its justfile. Constraint measured with just 1.58.0: an `import` cannot redefine a recipe, so the generated file calls named extension
points the repo defines (`lint: lint-extra`); a missing one fails at load. Drift check = re-render and compare. Replaces the justfile
comparison in `tools/preset_drift.py`. Whether to use `mod` (namespaced, wrappable) instead of `import` is decided in task 8.

## Rejected

- Language-prefixed commands (`blueprint python test`): breaks in a mixed repo and multiplies commands per stack.
- Keeping the regex-in-`just check` as the test and coverage contract: both consumers overrode it.
- One shared base justfile copied verbatim: cannot express multiple stacks without rendering.

## Risks and unknowns

- Node/go/rust layering tools are not researched; D2's Node column is a placeholder.
- Behaviour of a2kay's gate on the expired coverage override was not checked.
- A rendered justfile is a new generated artefact; the constitution says indexes are derived, never edited, which fits, but the review must confirm
  the repo-owned part stays small.

## Addendum (task 2, 2026-11-20): what blueprint's own core needs from an adapter

Read against `profile.py`, `facts.py`, `runner.py`, `concerns/*.py` and the profiles `python-uv.toml` and `dotnet.toml`. The gate-side
interface (units, edges, fingerprint, runner) is in `docs/missions/gate-kit-package/dotnet-adapter.md`; D2 above is its summary.
This addendum is the other half: what the *auditor* needs. Nothing was run or changed.

### The three things the core asks of a stack

| core need | where it is today | what a stack supplies | python-uv | dotnet |
|---|---|---|---|---|
| **Profile loading** | `concerns/stack.py` `load_profiles(profiles/*.toml)`; `ROLES` is a fixed tuple | one TOML: per role `tool`, `install`, `config`, `gate`, `na`/`untested`, `alternative`, optional `requires` | `python-uv.toml` | `dotnet.toml`, the same roles (`types`, `coverage` as tools) |
| **Detection** (which stacks, where) | `profile.py` `_stack_files`: a hard-coded manifest table (`pyproject.toml`+`uv.lock`, `*.sln/*.slnx/*.csproj`, `flake.nix`, `package.json`, `go.mod`, `Cargo.toml`) | a manifest glob and a depth | `pyproject.toml` (+ `uv.lock` gives `python-uv`) | `*.sln`, `*.slnx`, `*.csproj` |
| **Roles to checkpoints** | `stack.roles` projects `(stack x role)` rows; `runner.py` applies overrides and expiry; `report.py` renders | nothing: it is generic over the profile data | same | same |
| **Checkpoints specific to one stack** | `python_pin.py`, `cli_parse.py`, `uv_tool.py`, `shell.py` register with `applies=` on the stack | an `applies` predicate and a check | three | none yet (dotnet logic sits inside `stack.py`, see below) |

Proposed adapter record for blueprint (extends D2, nothing for the gate side): `manifests` (glob, depth), `roles` (the profile file),
`extra_checks` (module registering stack-specific checkpoints), `facts` (how kind, surfaces and traits are read, see below). The first
two already exist as data or a table; moving the table into each profile file's `[detect]` section is the only structural change.

### Is any Python assumption in the core? Yes, at the edges; the role/profile/override/report path is neutral

Neutral (checked): `runner.py` (rows, overrides, expiry, audit/gate split), `report.py`, `concerns/stack.py` role judging for
`config` and `gate` (file presence and a regex over `just --dump`), `facts`-independent checks (`gate.*` bar the ones below, `knowledge.*`,
`secrets.*`, `agents.*`, `backlog.*`). Six profiles, three of them not Python, already run through this path.

Python-shaped (each with the place and what to do):

1. **Kind, surface and trait detection reads only `pyproject.toml`**: `profile.py` `_detect_kind` and `_runtime_dependencies`,
   `detect_frameworks` (walk for `pyproject.toml`), `facts.py` `cli` and evidence rules. A Node or .NET repo gets no kind and no surfaces,
   so `framework.mcp.*` and the `kind` field can never fire for it. Fix: facts become adapter-provided (`manifests` + a dependency reader).
2. **`concerns/tool_pins.py`** keys the pin of `uv` on the stack name `python-uv` and reads `[tool.uv] required-version`. Move the
   per-stack pin (`uv` for python-uv, SDK for dotnet via `global.json`, already special-cased) into the profile as a `pins` field.
3. **`concerns/gate_guards.py` `_SCRIPT`** finds guard scripts by `*.py` in `python3` or `uv run python` commands, so
   `gate.guards-have-red-tests` sees no script in a Node, Go or shell gate: silent pass. Fix: an adapter supplies a script-pattern or the
   check fails on an unknown command shape instead of passing.
4. **`concerns/gate_command.py`**: the remediation text branches on `python` and says `uv add --dev rust-just`. Text only; make the fix
   hint a profile field.
5. **`concerns/stack.py`** holds .NET SDK logic (`_dotnet_executables`, `_sdk_versions`, `_sdk_ok`, lines 277-350) inside the generic role
   judge. Not Python, but proof that stack code lives in the core; it belongs behind the `extra_checks` hook.
6. **Install hints** (`PYTHONPATH=<shelf>/packages/blueprint/src python3 -m blueprint ...`) assume blueprint itself runs in Python. That is
   the tool, not the audited stack; it stays (a Node repo still runs blueprint from a shelf clone or dev dependency, and
   `uv` is the shelf's own pin).

Verdict for task 2's acceptance ("no Python assumption sits in the core"): **not yet true**. Items 1 to 3 are real: they make a
non-Python repo pass or go blank silently, which design D4 forbids. 4 to 6 are cosmetic or placement. The role contract itself
(D1) needs no Python knowledge, so the interface above is enough for a second adapter; items 1 to 3 are the work that task 4 and task 5
(profiles for node, go, rust; mixed-stack) must include, each with a failing fixture first.
