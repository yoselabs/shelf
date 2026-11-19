# Design: blueprint outcome contracts across several stacks

## Facts read from code (not changed yet)

- `profile.py`: `State` = declared profile + overrides + settings; `detect()` takes declared stacks else `_stack_files()` (manifests). `Profile.stacks`
  is a tuple, so a repo with several stacks already works at detection.
- `profiles/*.toml`: one file per stack, each `[[role]]` has `tool`, `install`, `config` (files that must hold), `gate` (regex that
  `just check` must reach), optional `na` or `untested`, and `[[role.alternative]]`. All six profiles define the same 13 roles
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

Each reads `.pre-commit-config.yaml` and `.git/hooks`: tests in `pre-commit`; `pre-push` running anything other than the gate; the gate also
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
