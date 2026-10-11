# Nx round 2 (Nx 23.3.0, local createNodes plugin, no @nxlv/python, no project.json)

Worktree: .claude/worktrees/agent-a99dece4d21f8ebfc. Host: macOS with Defender + OrbStack; load average 25-50 during the
run, so wall times are pessimistic and noisy (one `nx show projects` = 15-135 s wall for ~1 s of Nx work; npx added
~60 s of that, `node_modules/.bin/nx` directly cut it to ~15 s). uv stayed 0.10.12 (Nx never needed uv's lock hashing).
Daemon, cloud, analytics off. Git-diff tests ran in a scratch CLONE (commits there only); nothing committed in the repo.

## Setup built
- `tools/nx-uv-plugin.js` (101 lines): globs `pyproject.toml` + `packages/*/pyproject.toml`, parses TOML (smol-toml),
  one project per member, edges from dependencies + optional-dependencies + dependency-groups, pytest11 plugin
  packages (bdd-tags) become a dependency of every other package. Targets per package: `test` (pytest on that package's
  tests/), `lint` (ruff check + format --check), `deps` (deptry, cwd = package). Root project `shelf`: guard, preset,
  blueprint, lint (tests tools conftest.py), typecheck (pyrefly), spell (codespell), fitness (pytest tests/), cov
  (whole-repo pytest + --cov-fail-under=65).
- `nx.json` (37 lines): plugin, local cache dir `.nx/cache`, no daemon/cloud, namedInputs (sharedGlobals = uv.lock +
  root pyproject.toml + conftest.py; pyDefault = project files + sharedGlobals; repoAll = workspace tree).
- One command: `npm run check` = `uv sync --locked --quiet && nx run-many -t guard,preset,blueprint,lint,typecheck,spell,deps,fitness,test --nxBail`.
  Also `check:affected` (nx affected, git diff) and `check:all` (same with `cov` instead of `test`; NOT run).
- Polyglot: `packages/hello-ts` (package.json + one node:test test). Nx infers its `test` target from the npm script
  with no plugin code; needs root `workspaces: ["packages/*"]`.

## Criteria

| criterion | result | evidence (tested unless marked read) |
|---|---|---|
| graph complete (6/6 edges incl. optional extra) | ✅ | Compared Nx's project graph to tools/affected.py's graph for all 52 packages: 0 diffs. Real edges 6 (lean-wire<-page-tsv<-mcp-result-wire, yaml-merge<-any-frontmatter, plus 2 more); any-frontmatter -> yaml-merge present. Plugin edge bdd-tags -> all matches affected.py's "plugin selects everything". Round 1's miss is fixed because the plugin reads optional-dependencies itself. |
| git-diff affected | ✅ | Real commits in a scratch clone, `nx show projects --affected --base=HEAD~1 --head=HEAD --withTarget=test`. leaf timefmt -> {timefmt}. lean-wire -> {lean-wire, page-tsv, mcp-result-wire}. yaml-merge -> {yaml-merge, any-frontmatter}. bdd-tags -> 52. docs-only -> 0 packages (only root `shelf` targets). Every set equals what tools/affected.py selects for the same diff. |
| root files | ⚠️ mostly ✅ | uv.lock, root pyproject.toml, conftest.py -> all 53 test projects (via sharedGlobals inputs; Nx's affected honours file inputs, round 1's "nothing" was missing inputs). tools/ and root tests/ change -> only `shelf` (fitness etc.), same as affected.py. docs -> `shelf` only. GAP: Makefile change -> only `shelf`; affected.py selects everything. Fixable by adding Makefile to sharedGlobals (1 line), not done; moot if the Makefile goes. |
| new package fail-closed | ✅ for selection, execution untested | New Python package (copy of timefmt, no config) -> immediately a project with test/lint/deps, selected by affected (`zz-new`). New TS package (package.json only) -> selected (`hello2-ts`). Caveat, reasoned not run: `uv sync --locked` fails until `uv lock` is re-run, which is loud, and the lock change retests everything. A package with no tests/ dir gets no test target silently (same as Makefile today). |
| uv.lock respected | ✅ | No other Python lockfile. Every task is `uv run --frozen --no-sync`, preceded by `uv sync --locked`. uv.lock is a global input: a lock change retests all python packages (measured with the first input set, which also selected the TS package; fixed afterwards by splitting inputs, selection not re-measured). `uv lock --check` still passes. |
| cache | ✅ | Cold full run 8m51s, 164 tasks, 0 hits. Unchanged rerun: 162/164 hit, 6.6 s Nx time (26 s wall incl. npm/uv/node start); the 2 misses are guard and blueprint, which I set cache:false (they read HEAD / bd). One-package change (timefmt): 155/164 hit, only timefmt lint/test/deps + root guard, preset, blueprint, typecheck, spell, fitness re-ran. Cost: fitness has repoAll input, so ANY change re-runs it: 8m23s on this host, so a one-package change cost ~8.5 min (the make flow also always runs `tests/`; parity, not a win). |
| replaces `make check` fully | ⚠️ ❌ not fully | Green: `npm run check` rc=0, 164 tasks, 8m51s cold on the host. Covers guard, preset, blueprint, lint, typecheck, spell, deps, tests (per-package, no xdist; fitness uses -n auto). Not done / not equal: (1) `check:all` with the 65% coverage floor not run (16 min); the floor is a whole-repo number so it is one uncached root task, not per-package. (2) The container path (`docker run` when Docker answers, ~1 min) is not wired; the image has no Node. (3) The Makefile cannot simply go: tests/test_affected.py, test_bootstrap_target.py, test_preset_drift.py, test_onboard_linter_preset.py read it, and blueprint's gate dry-runs `make -n check`. Kept it untouched. (4) tools/affected.py is redundant but its test stays. |
| polyglot | ✅ | hello-ts (node:test) wired as `test` beside the Python ones. Cold run covers both stacks in one command (164 tasks incl. hello-ts:test). Touch hello.ts only -> `run-many -t test`: 52/53 hit, only hello-ts re-ran. Python change -> hello-ts not selected (graph, no edge). After I split inputs (pyDefault vs default), uv.lock no longer retests the TS package. Friction found: a non-Python dir under `packages/*` BREAKS uv ("Workspace member is missing a pyproject.toml"); needs `exclude = ["packages/hello-ts"]` in root pyproject.toml per TS package (loud, not silent). Also needs root package.json `workspaces`, a Node dependency set (nx, typescript, smol-toml) and tests dir named `test/` (not `tests/`, or test_gate_covers_every_package would demand a testpaths entry). dotnet exists on PATH (/opt/homebrew/bin/dotnet) but was not tried. |
| footprint | ⚠️ | Added: nx.json 37, package.json 17, tools/nx-uv-plugin.js 101, package-lock.json 1530 (a second lockfile, Node only), packages/hello-ts 11 (trial only), runtime dir `.nx/` (1.6 MB) and `node_modules/` (90 MB, both gitignored). Edited: .gitignore +4, pyproject.toml +1 (uv exclude). Real config for Python = 155 lines + a 1530-line npm lock; 0 project.json; 0 edits to packages/*/pyproject.toml. |
| maturity | ⚠️ | Nx is mature; the Python side here is 101 lines of OUR plugin (CommonJS, uses the createNodesV2 API, which has changed across majors) rather than a supported plugin. No Python-aware hashing: python tool versions are covered only through uv.lock. Nx 23 puts cache/db in ~/.nx unless cacheDirectory and NX_WORKSPACE_DATA_DIRECTORY are overridden (I left one; see cleanup). Output goes silent under non-TTY until the run ends. |

## Other measured facts
- `nx affected` inside the dirty worktree (`--base=HEAD`) selected all 164 tasks because the uncommitted package.json/pyproject changed; with 162 cache hits it finished in 20 s.
- Cold run critical path was fitness (6m49s); then 52 pytest processes at parallel=6. Per-package pytest without xdist.
- A lint failure injected in timefmt stopped the run (`--nxBail`) with the right task named: the gate is fail-closed on failures.
- git checkout in the worktree triggers a prek post-checkout hook that exits 1 (no config); unrelated to Nx.

## Verdict
Nx with a 101-line local plugin does what round 1 said it could not: finds all projects and all 6 edges with no
project.json, gives affected sets identical to tools/affected.py for every git-diff scenario, honours root files
through inputs, caches 99% on a rerun, and runs a TS package next to the Python ones in one command. It does not yet
replace `make check` as a drop-in: the Makefile gap, the coverage floor and the container path are open, it adds Node
plus a 1530-line npm lock and a uv `exclude` per non-Python package, and the whole-repo gates (fitness 8 min,
pyrefly) re-run on any change. ✅ viable as the polyglot/cache layer; ❌ not a clear win while the repo is Python-only.

## Cleanup
Removed ~/.nx/8a67aa6cc8dbc8ea (mine). Left: ~/.nx/f4c1e20031aa24ea (pre-existing, Oct 3, not mine); ~/.npm
(npm logs/cache stub; npm cache for installs went to scratchpad/npm-cache); ~/.cache/uv (reused by uv sync);
worktree-only: node_modules/, .nx/, the new files above (uncommitted); scratch clone at scratchpad/t2/clone.
