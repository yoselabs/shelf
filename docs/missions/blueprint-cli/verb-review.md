# blueprint CLI: verb review (shelf-cd9f)

Status: **awaiting the owner's approval of the target list below.** No code has changed for it.
Rules applied: no backward compatibility; condensed, encapsulated, opinionated, good out of the box.

## Today: 10 verbs, 3 audiences mixed in one `--help`

| audience | who types it | verbs |
|---|---|---|
| the owner or agent, day to day | by hand | `check` |
| the gate (justfile, hooks) | never by hand | `guard`, `preset`, `render`, `test`, `adr-index` (checker + hook), `check --gate` |
| setup, once per repo | by hand, rarely | `template`, `recipe`, `render` (first run), `preset --refresh` (shelf only) |
| the skill / curiosity | by hand | `checkpoints`, `survey`, `check --summary/--write/--audit/--json` |

The mix is the unintuitive part: a newcomer sees `guard` and `preset` beside `check` and cannot tell which one is the command.

## Rating

| verb | rating | reason |
|---|---|---|
| `check` | **keep**, the one daily command | Flags: keep `--repo --concern --audit --json --write`; rename `--gate` to `--brief` (what it prints); **remove `--summary`** (default output already groups by concern; the skill's use becomes `--write`). |
| `checkpoints` | **merge** into `check --list [prefix] [--json]` | It lists the same registry `check` runs; a second verb for a read-only view of the same thing. |
| `template` | **merge** into `init` | Copies missing `docs/agents/` files and the AGENTS.md block: that is setup. No one needs it apart from `init`. |
| `recipe` | **merge** into `init` (and the remediation text) | Prints a file for the user to redirect into place: a copy step init does itself. `init` writes hooks, `tools/*` scripts, rego, godot-test; nothing is printed to stdout for a human to pipe. |
| `render` | **hide** under `gate`, and `init` calls it | The justfile owns when it runs. A human never needs it; `just render` is the drift check. |
| `guard` | **hide** under `gate` | Hook and recipe entry only. |
| `preset` | **hide** under `gate` (`--refresh` stays shelf-only: moves to `tools/`, not shipped) | Same; the refresh is the shelf's own maintenance, not a consumer feature. |
| `test` | **hide** under `gate` | A gate step; `just test` is the entry. |
| `adr-index` | **hide** under `gate` | Generator the ADR checkpoint and the template call; `--write` is a maintainer step of the docs concern. |
| `survey` | **remove** from the CLI | One consumer, `docs/agents/working-with-agents.md`: the closed question set is skill data. The skill reads `survey.toml` itself; no verb needed, no code path kept. |

## Target: three public verbs, one hidden family

```
blueprint init     [--repo .] [--no-hooks]        # shelf-u7f4: detect -> audit -> plan -> apply what is missing
blueprint check    [--repo .] [--concern X] [--audit] [--json|--brief] [--write] [--list [prefix]]
blueprint gate <step> ...                         # not in the top-level help: guard | preset | render [--check] | test | adr-index
```

`blueprint --help` lists `init` and `check` and one line saying `gate` is for the justfile and hooks. Daily command stays `just check`;
`blueprint check` is for reading verdicts, `blueprint init` is for the first minute in a repo.

## Cost of the target

* `__main__.py` shrinks to three parsers (`gate` keeps its steps as sub-subparsers); `RECIPE_FILES` and `survey` code go.
* `.blueprint/base.just`, `.pre-commit-config.yaml`, the shelf justfile, `docs/*` and profile remediation texts: `blueprint guard|preset|render|test|recipe` become `blueprint gate ...` / `blueprint init`. One mechanical sweep, covered by `just check` (render drift, the hook-antipattern tests).
* Beads to file on approval: (1) fold `template`/`recipe` into `init` (lands with shelf-u7f4), (2) `gate` family + sweep, (3) `check --list` replaces `checkpoints`; drop `--summary`, rename `--gate` to `--brief`, (4) remove `survey`.

## Decisions the owner may flip

1. `gate` as a prefix versus keeping the four verbs top-level but hidden (`argparse` help=SUPPRESS). I recommend the prefix: one name to explain, and a hidden verb is still a verb.
2. Removing `survey` versus moving it under `gate`. I recommend removal.
3. `preset --refresh` leaving the package: it only ever runs in the shelf.
