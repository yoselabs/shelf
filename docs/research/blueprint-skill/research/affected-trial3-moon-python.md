# moon round 3: does `unstable_python` + `unstable_uv` remove round 2's hand work? (2026-10-11)

moon 2.6.1, python plugin 0.3.1, uv plugin 0.1.6 (the latest of each), uv 0.10.12, macOS host under load ~9.
Scratch clone: `scratchpad/clone3` (from the shelf's main 54e7ff2, commits there only; main checkout and the
round 2 worktree untouched). Verdict words: tested = I ran it, read = from plugin source / docs / GitHub, untested.

## Verdict

**No, not enough. It removes about 49 of the 52 generated files and the generator script, but not the two traps.**

- Generator: 3 of 6 edges are inferred, the 3 version-constrained ones are not (any-frontmatter -> yaml-merge,
  llm-cache -> anyllm, page-tsv -> lean-wire). Upstream bug, open: moonrepo/plugins#208 (2026-10-06). So the
  `dependsOn` for those must still be written, by hand (3 files, 2 lines each) or by a generator, and it fails OPEN:
  a new package that depends on `lean-wire>=0.2` gets no edge and serves a stale pass (tested).
- `cacheStrategy` trap: still there, unchanged (tested). Project edges, inferred or declared, do not make a
  dependent's hash see upstream source. The two-line `src` + `cacheStrategy: hash` fix from round 2 is still needed.
- `--affected` trap: still there (tested): `--affected` alone selects lean-wire only; dependents need
  `--downstream deep --include-relations`.
- `uv.lock`: moon DOES parse it, but only into direct production deps per project; dev deps and transitives are not
  hashed (tested fail-open), so `/uv.lock` stays a file input and every package re-runs on any lock change.
- Real gain: no `tools/moon_graph.py`, no 52 generated files, no generator-in-the-gate; install is managed.
  Footprint 8 files / 104 lines (round 2: ~60 files / ~280 lines), including 3 hand-written edges.
- Maturity: both toolchains are `unstable_*`, a 3-line GitHub-visible edge-inference bug and an open venv race exist.
  Net: strictly better than round 2 if you accept the 3 hand edges plus a guard; not a fix for the traps.

## Criteria

| # | criterion | result | evidence |
|---|---|---|---|
| 1 | infers deps from pyproject / uv workspace | partial, tested | Plugin reads `[project].dependencies` + `optional-dependencies` (extras included: `any-frontmatter` has `merge = ["yaml-merge>=0.1"]`) but only when the requirement has NO version specifier (`req.version_or_url.is_none()` in plugins/toolchains/python/src/tier2.rs; read). `[tool.uv.sources] workspace = true` is not consulted; dependency-groups are dropped (read). Measured with `moon query projects` and no moon.yml anywhere: 3 edges (content-extract->convert-md, http-cache->sqlite-resource, mcp-result-wire->page-tsv). Missing the 3 with `>=`/`>=,<` specifiers. Hand-writing those 3 `dependsOn` gave 6/6, identical to affected.py's edge set. A new package with `lean-wire` (no specifier) got the edge; with `lean-wire>=0.2` it did not. Env-marker form: untested. |
| 1b | can moon_graph.py + 52 moon.yml go | partly | moon_graph.py: yes, deleted. 49 moon.yml: yes (inherited tasks come from `.moon/tasks/all.yml`). 3 moon.yml: no, they stay (or a generator/guard for them). A guard that diffs `moon query projects` edges against `tools/affected.py` would make the gap fail closed: untested, not built. |
| 2a | uses the committed lock as-is | tested, with a config fix | Default: moon runs plain `uv sync --no-progress` (no `--locked`). With a stale lock (pyproject edited, lock not), it silently RE-RESOLVED AND REWROTE uv.lock (md5 changed) and the task then passed. Fix tested: `.moon/toolchains.yml` `unstable_uv: {syncArgs: ['--locked','--all-packages']}`; moon then ran `uv sync --locked --all-packages`, failed on the stale lock ("needs to be updated"), and left uv.lock byte-identical. |
| 2b | hashes only the resolved deps of each package | tested, but incomplete | `moon hash` manifest of page-tsv:test carries `unstable_python.dependencies.production = {lean-wire: "0.3.0", pydantic: <sdist sha256>}`. With `/uv.lock` removed from task inputs: flipping the ruamel-yaml hash in uv.lock re-ran yaml-merge:test only (3 other tasks cached); flipping pydantic re-ran lean-wire and page-tsv (both use it). But flipping pytest (dev dep, used by every package) re-ran NOTHING (4 of 4 cached) = fail-open; transitive deps are also absent (parse_manifest reads only `[project].dependencies`, read). A workspace sibling is hashed by its version string only, not its source. So `/uv.lock` must stay an input and the granularity is unused. |
| 3a | downloads a Python / uv | no by default, yes if pinned | Without `version`, `SetupToolchain` is "Skipped, using global commands on PATH" (tested, debug log): system python3/uv, nothing written to ~/.proto. With `version: '3.12'` / `'0.10'` (tested) moon installed proto 0.62.2, Python 3.12.15 and uv 0.10.12 into ~/.proto (202 MB, 21 s) and added `--no-managed-python --no-python-downloads` to uv venv/sync (plugin source). The pre-existing .venv (uv-managed 3.12.13) was kept, so interpreter and pin could drift apart. moon ignores `.python-version`. |
| 3b | who runs `uv sync` / venv | tested | Moon runs `uv sync` itself (an `InstallDependencies` action before the first task) and `uv venv .venv` only if `.venv` is missing. One workspace `.venv` at the root; no per-package venvs (`packages/*/.venv` absent). Re-runs the sync when the lock or a project's declared dependencies change (lock flip: re-ran; comment-only pyproject edit: did not). No conflict with `uv run --locked` in task scripts: both tasks and moon's sync worked on the same `.venv` and `uv run --locked` kept passing. |
| 3c | writes to ~ | tested | `~/.moon` (id, 1 plugin dir with 3 wasm, temp; 5.4 MB) and `~/.proto` (temp only; 202 MB if versions are pinned). Neither existed before; both removed after the trial (verified gone). |
| 4 | task inference | none, tested | `moon project` lists only tasks from our config (`check deptry src test`; root: `blueprint check fitness guard lint preset spell typecheck`). Plugin has no `extend_task_command` / `hash_task_contents` / task-detection hooks (`moon toolchain info`). All tasks still explicit. `uv run --locked` prefix still needed: only .venv/bin is added to PATH. |
| 5a | lean-wire edit | pass, tested | `moon run :test` with the config below: lean-wire, page-tsv, mcp-result-wire re-ran; 98 other tasks cached. |
| 5b | yaml-merge edit | pass, tested | yaml-merge + any-frontmatter re-ran, 100 cached (needs the hand edge). |
| 5c | timefmt leaf edit | pass, tested | timefmt only (102 cached). |
| 5d | uv.lock edit | not re-run | Same as round 2 (every package re-runs because `/uv.lock` is an input); only granular flips measured, see 2b. |
| 5e | new package depends on `lean-wire>=0.2` | FAIL OPEN, tested | No edge. Edit lean-wire, `moon run newpkg:test`: `newpkg:src` and `newpkg:test` both "cached" = stale pass. With plain `lean-wire` the edge appeared and lean-wire:src ran. |
| 5f | cacheStrategy trap | still present, tested | S0 run: plugin on, edges declared, NO `src` trick. After a lean-wire edit, `page-tsv:test` and `mcp-result-wire:test` were "cached"; only lean-wire re-ran. The hash manifest shows `projectDeps: [lean-wire]` as a name only. Fix = round 2's `src` + `cacheStrategy: hash`, kept in C1. |
| 5g | `--affected` trap | still present, tested | After a committed lean-wire edit: `--affected` = lean-wire:src, :test only; `--downstream deep` adds lean-wire:check/deptry, still no dependents; only `--downstream deep --include-relations` adds page-tsv and mcp-result-wire (12 tasks). Safe command remains plain `moon run :check`. |
| 6 | maturity | read | Both are `unstable_python` / `unstable_uv` (the docs list them with the `unstable_` prefix; no stability doc besides the name). Plugin releases: python 0.3.1 and uv 0.1.6 "support moon v2.6", latest tag 2026-10-04; moon 2.6.1 released 2026-10-07. No warnings printed by moon in the cold run (tested). Open issues touching it: moonrepo/plugins#208 (this edge bug, 1 week old, previous report #2411 closed 2026-03 as fixed for extras but the version check stayed), moonrepo/moon#2653 (concurrent env setup races on the shared workspace .venv on a cold `moon ci`: `uv venv` collision, 12 comments; a cold CI with no .venv is untested here), moonrepo/moon#2143 (uv recreates the venv in docker images). Closed in the last 8 months: ~12 python/uv bugs (docker setup, pinned versions ignored by uv sync, `load_versions` aborting every run in 2.5.x #2678). Python toolchain bug rate is high; rate of fixes is also high. |
| 7 | git-ref installability | pass, tested | `git diff 54e7ff2 -- 'packages/*/pyproject.toml'` is empty: no per-package pyproject edit needed. Only extra files are the 3 `packages/*/moon.yml`, which `#subdirectory=` installs ignore. The root `pyproject.toml` needed no edit either (round 2's `exclude` was only for the hello-ts TS package). |
| 8 | footprint | tested | vs 54e7ff2: 8 files, 104 lines added: `.moon/workspace.yml` 9, `.moon/toolchains.yml` 5, `.moon/tasks/all.yml` 34, `moon.yml` 49, 3 x `packages/*/moon.yml` (2 lines each), `.gitignore` +1 (`.moon/cache/`). Round 2: ~60 files / ~280 lines. |

Cold run (the one allowed full gate), config C1, `moon run :check` from the clone: rc 0, 216 tasks, 191 s wall
under load ~9 (all 52 packages' test + deptry, plus guard, preset, blueprint, lint, typecheck, spell, fitness).
Warm: 3 s, 214 cached (guard and blueprint are uncached by design). No make-check baseline timed.

## Config that was run (C1)

- `.moon/toolchains.yml`: `unstable_python: {packageManager: uv}`, `unstable_uv: {syncArgs: ['--locked','--all-packages']}`
  (no versions: system python3/uv).
- `.moon/tasks/all.yml`: round 2's file unchanged (`src` noop with `deps: [{target: '^:src', cacheStrategy: hash}]`,
  `test` with `deps: [{target: '~:src', cacheStrategy: hash}]`, inputs include `/uv.lock`).
- root `moon.yml`: round 2's minus the `graph` task and its `moon.yml` inputs.
- `packages/{any-frontmatter,llm-cache,page-tsv}/moon.yml`: `dependsOn: [yaml-merge|anyllm|lean-wire]`.
- Deleted: `tools/moon_graph.py`, 52 generated `moon.yml`, hello-ts (not needed for this question).

## Pitfalls hit

- Plain `uv sync` by moon rewrites a stale `uv.lock` silently (tested). Set `syncArgs` with `--locked`.
- `syncArgs` replaces moon's own default flags (`--no-progress`), so spell them out (read: tier2.rs).
- The install action is skipped when moon's own hash of manifests/lock is unchanged, so a stale lock can still
  surface only in the task's `uv run --locked` (it does: tested, rc 2) rather than in the install step.
- `version:` pins pull proto, Python and uv (~140 MB) and switch uv to `--no-managed-python`; skip them unless you
  want moon to own the interpreter. moon does not read `.python-version`.
- Pristine main's `uv.lock` is stale right now (any-proc v0.1.0 vs v0.1.1, from commit 74d6924): `uv lock --check`
  fails on a fresh clone. I ran `uv lock` in the clone only. Worth a real fix in the repo (not touched here).
- The `unstable_python` dep hash covers direct production deps only; do not drop `/uv.lock` from inputs.
- Round 2's pitfalls (`__pycache__` globs, `:task` scopes not allowed in `deps`, absolute `$projectRoot` in hashes,
  `.moon/cache/` ignored) all still apply: the config was reused as is.

## Left behind

- Removed `~/.moon` and `~/.proto` (neither existed before the trial; checked gone). Nothing else outside scratchpad.
- Main checkout `~/Workspaces/shelf` and the round 2 worktree: read only, untouched.
- Scratchpad: `clone3/` (own `.venv`, 5 local commits, nothing pushed), `p3-*.log`, `p3run.sh`, `edges3.py`, `plugsrc/`
  (downloaded plugin sources for reading), `tc.bak`, `p3-first.log`.
- Untested: env-marker dependencies, cold CI with no `.venv` (#2653 race), docker/container run, coverage floor,
  .NET package, the `--locked` fail-closed path on a stale lock through the install action itself (the task's own
  `uv run --locked` failed first; the install-step failure was seen only after a manifest dep change), a guard
  script for the 3 hand edges.

## Recommendation to the caller

Python support is worth turning on only for what it does well: managed `uv sync --locked --all-packages`, no
per-package files for unversioned edges, and a hash that already knows the resolved direct deps. It does not change
the adoption math from round 2: the `cacheStrategy` line and the `--include-relations` rule are still the two things
a user must know, and the versioned-edge gap (3 of 6 here, more as packages gain bounds) is a fail-open that needs
either a guard (diff `moon query projects` against `tools/affected.py`) or waiting for plugins#208. If moon is still
under consideration, track #208 and re-test; if it is fixed, the generator and all 55 per-package files disappear.
