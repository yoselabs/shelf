## Today (measured 2026-11-21)

- `model.REGISTRY` holds 53 registered checks, each with `concern` (its module), `layer`, `applies` (a predicate over the profile)
  and `audit_only`. Stack and framework rows (`stack.<stack>.<role>`, `framework.<name>.<role>`) are generated at run time from
  `profiles/*.toml`, so they are already data-driven and already detected.
- `concerns/__init__.py` lists 14 modules; importing one registers its checks.
- `profile.py` detects the stack from files and sets `tracker="beads"` when `.beads/` exists. `blueprint.toml` carries the declared
  profile, per-row overrides (with reason and expiry) and per-check settings.

## The split, by who owns each row today

| plugin | rows now (module) | default | requires |
|---|---|---|---|
| beads | all `backlog.*`, `hooks.beads-sync`, `agents.bd-metrics-off`, `agents.session-hooks`, the bd half of `gate.git-remote` | on | git-hooks |
| git-hooks | the other `hooks.*`, `gate.hooks-installed`, `gate.hooks-recipe` | on | |
| gate | the other `gate.*` (one-command, runner, clean-clone, step-inputs, no-ci, lfs) | on | git-hooks |
| agents | `agents.instructions`, `agents.worktrees*` | on | |
| mise | `stack.tool-pins`, `stack.agent-cli-pins`, `secrets.scanner` pin half | on | |
| secrets | `secrets.*` | detected (sops or gitleaks present) | mise |
| python | `python_pin`, python-uv profile rows | detected | mise |
| uv | `uv_tool`, uv rows | detected | python |
| dotnet, node, go, rust, nix, compose, dockerfile, shell | profile rows (data) | detected | mise |
| frameworks (godot, mcp, unity) | `framework.*` | detected | its stack |

Three rows straddle two plugins today (`gate.git-remote`, `secrets.scanner`, `gate.hooks-recipe` names bd). Each straddle is
resolved by giving one plugin the row and the other a `requires`, never by letting one plugin read another's internals.

## Shape

A plugin is a manifest (data) plus the rows it owns:

```
id, title, default (detected|on|off), requires [ids], detect (a fact or file rule, for detected),
rows [row ids], recipes [files init writes], settings keys
```

- The manifest is TOML next to the plugin's code. blueprint ships its own; a third party ships theirs the same way.
- A row belongs to exactly one plugin. A test fails a row with no plugin or two.
- Resolution order: repo switch (`blueprint.toml`) beats default; `requires` is applied last (a dependent of an off plugin is off).
- `blueprint check --list` and the audit report show the plugin of each row and why a plugin is off ("switched off in blueprint.toml",
  "requires beads").

## Keeping it simple

1. **Data before code.** Step 1 adds the manifest and a `plugin` column on each row, derived from today's module. No row changes
   behaviour and no repo is asked anything new. The audit of a2kay and shelf gives the same verdicts before and after.
2. **One direction.** A plugin may use `blueprint.model` and its own files. It may use another plugin only through a declared
   `requires`, and an architecture test (`just arch`) enforces it. This is the guard against the mixing the owner fears.
3. **Move last.** Code moves into per-plugin folders only after 1 and 2 hold, one plugin per change, each green on its own.
4. **No second config language.** The switch is one table in the existing `blueprint.toml`.

## Open questions

- Does an `off` plugin's recipes still get written by `blueprint init`? Proposed: no.
- Are the framework profiles plugins or settings of their stack? Proposed: settings of their stack, shown as sub-rows.
- Where do third-party plugins load from (a path in `blueprint.toml`, or an installed package entry point)? Proposed: a path first.

## Step 1 as built

`packages/blueprint/src/blueprint/plugins/*.toml` (18 manifests) and `plugins.py`. Differences from the table above, found while
assigning every row:

- A `stacks` plugin (default on) owns the rows shared by every language: `stack.roles`, `stack.one-owner`, `stack.shelf-sources`,
  `framework.roles`. Every stack requires it.
- `python` owns the python-uv profile rows and the python pin rows; `uv` owns only `stack.python-uv.uv-tool` today, because the profile
  is one stack named python-uv. Splitting uv further waits for a profile split.
- `frameworks` is one plugin for godot, mcp and unity, not three; it requires `stacks`.
- Hand-written rows are listed by id, never by glob, so a new row with no owner fails `test_plugins.py`; generated stack and
  framework rows use `stack.<name>.*`.
- `blueprint check --list` shows the plugin of each row. Nothing else reads the manifests yet.

## Steps 2 and 3 as built

- `[plugins]` in `docs/blueprint/blueprint.toml`: `beads = false`. Only booleans; an unknown plugin or a non-boolean is a problem the run reports.
- `plugins.resolve` gives the plugins NOT asked, each with why: switched off, off by default and not switched on, or `requires X` where X is
  not asked. The runner drops those plugins' checks and the rows of theirs that another check reports (`stack.roles` reports
  `stack.<name>.<role>`), and prints one notice per plugin not asked. `set_hash` counts only the asked checks.
- The requires graph after assigning real imports: beads and gate require git-hooks; gate and mise require stacks; every stack, python's uv and
  frameworks require stacks (python also for uv). mise is NOT required by the stacks: a repo that pins no tools still wants its stack rows.
- Each manifest lists its `modules` (the `concerns/*.py` files it owns until step 5). `tests/test_arch_plugin_imports.py` (any-arch Rule, no
  rows) fails a concern module importing another plugin's module without a `requires`, and a module no plugin owns.
