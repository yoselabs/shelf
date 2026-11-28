---
id: 0035
title: Tool config lives in .config/, caches in .cache/, deploy files in deploy/
statement: Tool config leaves the repo root for .config/, caches for .cache/, deploy files for deploy/, unless the tool cannot, moving breaks it, or it is an IDE or ecosystem file.
concerns: [gate, packaging]
status: accepted
decided_by: owner
updated: 2026-11-28
distilled_into: N/A — self-enforcing via the blueprint audit row layout.root-files-in-config and the flags the rendered recipes pass
---

# 0035 — Tool config lives in `.config/`

Owner decision 2026-11-28 (bead shelf-mkfd). Extends ADR 0034: the root holds repo-level files only.

## Decision

A tool's config file or folder moves out of the repo root, **unless** one of three holds (the exception test):

1. **Cannot**: the tool reads no other location and has no flag or environment variable for one.
2. **Breaks**: moving makes the tool misbehave (it finds nothing, or finds a different file).
3. **IDE or ecosystem file**: an editor, a package manager or the language ecosystem discovers it at the root (`package.json`, `pyproject.toml`, `uv.lock`, `justfile`, `.python-version`, lockfiles, `.gitignore`, `.gitattributes`, agent folders).

Where it goes:

| what | where |
|---|---|
| tool config files | `.config/<tool>.<ext>` |
| tool caches (every cache and data file a run writes) | `.cache/<tool>` (one ignored folder) |
| Dockerfile and compose spanning projects | `deploy/` |
| Dockerfile building one project | that project's folder |
| infrastructure as code (Terraform, Pulumi) | `infra/` |

**The row** `layout.root-files-in-config` (waivable, ADR 0018) lists the root files that could move with the exact `git mv`, and the cache settings still at a tool default with the exact setting. It judges **only what the engine reads in the new place too**: a file a repo cannot move never fails it. Rendered recipes and the secret scan pass the flag when the file is in `.config/` (`hadolint -c`, `yamlfmt -conf`, `dclint -c`, `gitleaks --config`); `lint-imports --cache-dir` and `HYPOTHESIS_STORAGE_DIRECTORY` always point at `.cache/`.

**Rollout:** the pin (ADR 0018). A repo on an older pin is unaffected; at the bump it moves or waives.

## Measurements (2026-11-28, each tool run for real from a scratch repo)

| candidate | tool | finds it in the new place with no flag? | flag or env that works | editor discovery risk | verdict |
|---|---|---|---|---|---|
| `.gitleaks.toml` | gitleaks 8.30.1 | no (reads root only; `dir .` found 0 leaks) | `-c/--config`, `GITLEAKS_CONFIG` (both found the rule) | none: no editor reads it | moves to `.config/gitleaks.toml` |
| `.hadolint.yaml` | hadolint | no (`.config/` ignored: DL3018 still raised) | `-c/--config` (DL3018 ignored as configured) | untested: the VS Code extension needs its own config-path setting | moves to `.config/hadolint.yaml` |
| `.yamlfmt.yaml` | yamlfmt 0.21.0 | no (indent 4 ignored) | `-conf` (indent 4 applied) | YAML editor extensions: none read it | moves to `.config/yamlfmt.yaml` |
| `.dclintrc` | dclint 3.1.0 | yes for `.config/dclintrc.json` (cosmiconfig search found it) | `-c/--config` (rule off as configured; a missing file is an error, not a silent pass) | none | moves to `.config/dclintrc.json` (pass `-c` anyway) |
| `typos.toml` | typos | no (a misspelling still flagged with `.config/typos.toml` present) | `-c/--config` (clean) | typos VS Code extension has its own config setting | moves to `.config/typos.toml` |
| `.pre-commit-config.yaml` | prek 0.5.5 | no (error: no config found) | `-c/--config`; `prek install -c` bakes `--config=` into every hook shim | none | **may move; engine not yet** (10 readers: bead) |
| `mise.toml` | mise 2026.10 | yes (`.config/mise.toml` is in mise's search path) | none needed | none | **may move; engine not yet** (tool pins, render, tests read `mise.toml`) |
| `gate-inputs.toml` | any-gate (ours) | n/a: ours | the reader names the path | none | **may move; engine not yet** (any-gate reads the root) |
| `.blueprint/` | ours | n/a: `import '.blueprint/*.just'` is a path in the justfile | the justfile import | none | **may move; engine not yet** (render, guard, drift read `.blueprint/`) |
| `.ruff_cache` | ruff 0.17.2 | n/a | `[tool.ruff] cache-dir`, `RUFF_CACHE_DIR` (cache under `.cache/ruff`, none at root) | none | moves (row judges `cache-dir`) |
| `.pytest_cache` | pytest | n/a | `[tool.pytest.ini_options] cache_dir` works, but with `-p no:cacheprovider` (the gate's own runs) the option is unknown: `PytestConfigWarning`, an error under `filterwarnings = ["error"]` (measured in the shelf gate) | none | **stays** (exception b); the row does not judge it |
| `.coverage` | coverage | n/a | `[tool.coverage.run] data_file`, `COVERAGE_FILE` | none | moves (row judges `data_file`) |
| `.hypothesis` | hypothesis 6.165 | n/a | `HYPOTHESIS_STORAGE_DIRECTORY` (no settings key) | none | moves (rendered `export` in `.blueprint/python.just`) |
| `.import_linter_cache` | import-linter | n/a | `lint-imports --cache-dir` (no config key) | none | moves (rendered recipe passes it) |
| `justfile` | just | **no**: `just a` → "no justfile found"; works only with `--justfile` in every call | `--justfile` | editors and `just` itself discover the root file | **stays** (exception 3 and 2) |
| `Dockerfile`, `compose.yml` | docker | n/a: `-f deploy/compose.yml` and `build -f deploy/Dockerfile` both ran (compose `config` printed project `deploy`; `build --check`: no warnings) | `-f` in every call | VS Code Docker extension finds `**/Dockerfile` and `**/compose*.yml` in subfolders | move to `deploy/` (decided; **engine not yet**: stack detection, image steps, pin checks read the root) |

dockerfmt and the `images` step's BuildKit `--check` take the file path as an argument, so they follow the folder. dclint, hadolint and yamlfmt take their config by flag, as above. Not measurable here: the VS Code extensions (no editor in the measurement); their risk is stated from the extension settings, marked untested.

## One config per tool (owner, 2026-11-28)

"We don't want copies of the same configuration file over a multi-folder repo; if we have rules, they apply to everything; define a config once."

- A tool's config is defined **once per repo**: a cross-cutting repo tool in `.config/` (the rendered recipe passes the flag; the justfile is the one place that names which config applies), a per-language tool in that project's manifest.
- A project that differs **extends** the shared base and carries only the delta.
- The row `layout.one-config-per-tool` (waivable, ADR 0018) flags one tool configured in two folders with the same settings (at least 70% of the settings equal, at least 3 settings each), reports the pair and names the extend mechanism, or says `cannot extend: waive`. A file that already extends is a delta, not a copy.

| tool | extends a base? |
|---|---|
| ruff | yes: `extend = "<path>"` (ruff.toml or `[tool.ruff]`) |
| tsconfig, biome, eslint (`.eslintrc.json`) | yes: `"extends"` |
| gitleaks | yes: `[extend] path` |
| hadolint, yamlfmt, dclint, typos, prettier | not verified; the row treats them as `cannot extend: waive` (prettier shares by package reference) |

**Corpus (42 repos): 0 repos have the duplication at the 70% line.** 4 repos define one tool twice; the closest pair is 62% (fullstack-web-typescript-wasp), the rest 19% and below. The row is a guard, not a current failure.

## Where Dockerfile and compose go: `deploy/` or `docker/`

Research pass (21 well-known repos, 2026-11-28, indicative): compose at the root in about 11, in `docker/` in about 6 (immich, supabase, n8n, documenso), in `deploy/` in 3 (cal.com, appsmith, plane; there it holds several deploy targets or only scripts), `infra/` in none. So `docker/` is the second most common home and `deploy/` the minority one. The owner's recommendation stays `deploy/` (runtime topology spanning projects) with `infra/` for IaC only; `docker/` is the named alternative, and the engine accepts both when it follows (bead). This ADR does not change the rule on the research's counts.

## Where the measurements confirm or contradict the research

- **Confirmed:** only mise finds `.config/` by itself (dclint also finds `.config/dclintrc.json`, which the research did not list); gitleaks, typos, prek, hadolint and yamlfmt need a flag; `just` finds no justfile outside the root.
- **Contradicted:** "do not support it" for those five tools. Each worked with its flag in a real run; the cost is a flag in every recipe and hook that runs the tool, and the audit remedy says so.
- **Not measured:** editor extensions, and `docker/` discovery beyond `-f`.

## Rejected

- **Moving `justfile`, `mise.toml`-class pin files to be flag-driven everywhere**: `just` finds no justfile outside the root without `--justfile` on every call (measured); an editor integration file is exception 3.
- **A row that lists every candidate before the engine follows it**: a repo would be failed for a move that breaks the gate. The row grows with the engine, one source of truth: `MOVABLE` in `concerns/layout/root_files.py`.
- **A compat shim that reads both places forever**: the engine reads `.config/` first and the root second only while repos on older pins move.

## Follow-ups (not in this change)

Engine support, then add each to the row: the hook config (`prek -c`), `mise.toml` / `mise.lock`, `gate-inputs.toml`, `.blueprint/`, and `deploy/` for Dockerfile and compose.

## History

- 2026-11-28: decided by the owner; measured; shelf's own root moved (`.gitleaks.toml`, the five caches).
