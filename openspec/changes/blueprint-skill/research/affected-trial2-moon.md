# moon, round 2: can it replace `make check` on the shelf? (2026-10-11)

moon 2.6.1 (npm `@moonrepo/cli`, the current release), macOS host, uv 0.10.12, Node 24.14. Worktree
`.claude/worktrees/agent-a6331229b8f5cdbca` holds the config; all git-diff and cache runs were done in a
scratch CLONE (`scratchpad/clone`, commits there only). Tested = ran it. Read = from moon docs.

## Verdict

✅ for correctness, ⚠️ for adoption. With `cacheStrategy: hash` on two task deps plus a generated per-package
`moon.yml`, moon re-runs dependents correctly (the round 1 failure is fixed, measured), covers all 52 packages plus
a TypeScript one, fails closed on a new package, and cuts a warm run to 5-7 s. The price: 53 generated
`moon.yml` files (+ a generator that must stay in the gate), a second tool that reads pyproject by script instead of
natively, and `unstable_*` Python toolchains that we bypass entirely. Cleaner than round 1, still not free.
Turborepo remains the comparison; this is no longer "moon is broken".

## Why round 1 failed, and the fix (the answer to the question)

Cause 1 (graph): moon infers nothing from a uv workspace. 3/6 edges in round 1 came from elsewhere; `lean-wire>=0.2`
was invisible. Fix: `tools/moon_graph.py` (50 lines, stdlib, reuses `tools/affected.py`'s graph incl. extras and
dependency groups) writes `dependsOn` into each `packages/<p>/moon.yml`. 6/6 edges confirmed through
`moon query projects`.

Cause 2 (stale cache), found in moon's own hash manifest (`moon hash <h>`): `"deps": {"lean-wire:src": "ignored"}`.
Docs (https://moonrepo.dev/docs/config/project, `cacheStrategy`, v2.3.0): a task dependency WITHOUT declared outputs
defaults to `ignored`: "The dependent task is never invalidated by this dependency." That is the silent stale pass.
Fix, two lines in `.moon/tasks/all.yml`:

```yaml
src:   {command: noop, deps: [{target: '^:src', cacheStrategy: hash}], inputs: ['@group(pkg)']}
test:  {deps: [{target: '~:src', cacheStrategy: hash}], ...}
```

`src` is a no-op whose only job is its hash: own files plus the same task of every project dependency, so the hash
covers the transitive closure. No `inputs: ['/packages/<dep>/**']` lists, no per-edge hand work. Other routes
considered: `inputs` with `@dirs` (needs per-package lists = the generator again, and does not chain through
transitive deps); `--downstream` (see affected row: not enough alone).

## Criteria

| criterion | result | evidence |
|---|---|---|
| graph complete (6/6) | ✅ tested | `moon query projects`: 6 edges identical to `tools/affected.py` (any-frontmatter→yaml-merge, content-extract→convert-md, http-cache→sqlite-resource, llm-cache→anyllm, mcp-result-wire→page-tsv, page-tsv→lean-wire). Only because the generator writes them; moon infers none. A specifier (`lean-wire>=0.2`) is handled: the new-package run below used one. |
| dependents re-run on upstream change (no stale cache) | ✅ tested | Real edit to `lean-wire/src/lean_wire/__init__.py`, plain `moon run :check`: re-ran lean-wire, page-tsv, mcp-result-wire tests, 49 other package tests cached. Before the `cacheStrategy` line: page-tsv and mcp-result-wire `cached` (reproduced round 1). Edit to yaml-merge re-ran any-frontmatter:test. Edit to leaf timefmt re-ran timefmt only. A new package depending on `lean-wire>=0.2` re-ran on a lean-wire edit. |
| git-diff affected | ⚠️ tested | `moon run :check --affected --base HEAD~1 --head HEAD` after a committed lean-wire edit: 4 tasks, lean-wire only. Adding `--downstream deep`: still 4 (the dependents are NOT added). Only `--downstream deep --include-relations` gave page-tsv + mcp-result-wire + the root gates (21 tasks). So `--affected` alone is fail-open on dependents; the safe command is plain `moon run :check`, where the cache is the affected computation (hashing 219 tasks costs ~5 s). Docs-only commit with the full flags: 9 tasks, root gates only, no package tests. |
| root files | ✅ tested | `uv.lock` edit: all 52 Python `test`+`deptry` re-ran, `hello-ts` cached. `conftest.py` edit: all 52 tests re-ran. `Makefile` edit: fitness (+ lint, unexplained, over-run not under-run). `tools/` edit: lint, typecheck, spell, fitness, no package tests. Root `pyproject.toml` is in every test's inputs (read from config, not run separately). Note `uv.lock` is read as a file input, not understood: any byte change re-runs everything, same as `tools/affected.py`. |
| new package fail-closed | ✅ tested | Added `packages/newpkg` with no `moon.yml`: moon auto-discovers it and the inherited `test` runs (`moon run newpkg:test` ran; failed on stale `uv.lock` via `--locked`). `shelf:graph` (`moon_graph.py --check`) failed the gate at once: "stale or missing moon.yml: newpkg". After `moon_graph.py` + `uv lock`: newpkg:test and deptry ran, dependsOn lean-wire generated. A directory with neither pyproject nor moon.yml also fails `moon_graph.py --check` (tested: rc=1). The new-package scenario ended RED on the full gate even after moon.yml and the lock were fixed: `shelf:fitness` failed on `test_gate_covers_every_package` (newpkg not in the hand-maintained `testpaths`) and `test_catalog_release_is_current` (no `catalog/` entry). Those are the repo's own fail-closed layers, and they work under moon; newpkg:test itself passed. The global `.moon/tasks/all.yml` (not per-language) is what makes the default "tested". |
| uv.lock respected | ✅ tested | Every task is `uv run --locked ...`: a stale lock fails (seen on newpkg), nothing resolves behind the lock. `uv.lock` is an input of every Python test/deptry hash. moon never installs Python: no `unstable_python`/`unstable_uv`; `language: python` only labels projects. `uv sync` stays the owner of the environment (moon does not run it; a missing sync = `uv run --locked` error, not a pass). |
| cache | ✅ tested | Unchanged rerun: 5-7 s, 217/219 cached (the two uncached are `guard` and `blueprint`, which read git HEAD / the tree, `cache: false` by design). One-package change (leaf/extra): 8-10 s. Shared change with 3 dependents: 16-27 s. Cold full run: 3m36s (calm host), 13m13s and 20m41s while 3 other sessions loaded the machine (load 25-50): host timings are noise-dominated, as the Makefile already says (10-17 min). |
| replaces make check fully | ⚠️ tested, one gap | `moon run :check`, green, 219 tasks: guard, preset, blueprint, graph, ruff check+format, pyrefly, codespell, fitness (`pytest tests`), deptry x52, pytest x52 + hello-ts. Not replicated: (1) the `--cov-fail-under=65` floor (only `check-all` has it; per-package runs run `-p no:cov`; combining `.coverage` files from cached runs needs outputs plumbing, untested); (2) the Docker container path (`make check` prefers it on macOS; moon ran on host); (3) pytest-xdist: moon runs 1 pytest per package with `-n` absent, parallelism is across packages (host cold runs were not faster than make's 10-17 min). (4) `testpaths` stays hand-maintained: moon never reads it, but `tests/test_gate_covers_every_package.py` still demands it, so it is a pure adoption cost (a package must be added to `testpaths` and to `catalog/` to turn the gate green; see new-package row). |
| footprint | ⚠️ | 53 `packages/*/moon.yml` (52 generated, 128 lines total, + `hello-ts` by hand), root `moon.yml` 54 lines, `.moon/tasks/all.yml` 34, `.moon/workspace.yml` 9, `.moon/toolchains.yml` 1, `tools/moon_graph.py` 50; 1 line `.gitignore` (`.moon/cache/`); no edit to `packages/*/pyproject.toml`; polyglot needs 1 line in root `pyproject.toml` (`exclude`). ~60 files, ~280 lines. Generated files live in git and must be regenerated whenever a dependency changes; the `graph` gate enforces it. moon downloaded a 1.3 MB wasm plugin to `~/.moon` on first run (network at first use). Binary via npm; no Node needed at run time except for TS packages. |
| polyglot | ✅ tested (TS), .NET untested | `packages/hello-ts` (package.json, `src/hello.ts`, `test/hello.test.ts`, node:test, Node 24 strips types) + 12-line hand-written `moon.yml` with its own `test` and `check`. `moon run :check` runs Python and TS in one command, one graph, one cache. Python edits (lock, lean-wire, conftest): `hello-ts:test` stayed cached. A `hello.ts` edit: `hello-ts:test` re-ran, no Python package test did. Findings: (a) uv's `members = ["packages/*"]` breaks on any non-Python directory ("missing a `pyproject.toml`" in every `uv run`, `make check` included): needs `exclude = ["packages/hello-ts"]` in the root pyproject, one line per non-Python package, or a different directory; (b) the generic spell gate reads `packages/**` and reran on the TS edit (correct: codespell covers it); (c) `.NET`/dotnet was on PATH but not tried. (d) the TS package is invisible to `tools/affected.py` and pyrefly/ruff, those stay Python-only. |
| maturity | ⚠️ | Python toolchains are named `unstable_python`, `unstable_pip`, `unstable_poetry`, `unstable_uv` and "This toolchain requires the unstable_python toolchain to also be enabled." (https://moonrepo.dev/docs/config/toolchain). We use none of them: the result stands on moon's generic task graph and cache, not on its Python support. `cacheStrategy` has existed since v2.3.0; the safe-looking default (`ignored` for no-output deps) is a trap that cost a whole round. `--affected` + `--downstream` silently omitting dependents is a second trap. Version drift risk on moon upgrades: pin `2.6.1` in CI. |

## Pitfalls hit (for whoever adopts it)

- Default `cacheStrategy: ignored` on output-less deps (stale pass). Fix: `hash`.
- `--affected --downstream deep` does not pull in dependents; needs `--include-relations`. Prefer no `--affected`.
- Glob inputs under `/tools/**` include `__pycache__` (untracked, ignored): fitness reran on every run until `'!/**/__pycache__/**'` was added.
- Target scopes `:task` are not allowed in a task's `deps` (error), so the one command is a task NAMED `check` in every project (`moon run :check`), not a root aggregate.
- `.moon/cache/` must be gitignored or `--affected` sees cache writes as changes.
- `$projectRoot` expands to an absolute path inside `script`, so hashes differ per checkout: a shared remote cache across clones would not hit for tests.
- Gate-of-the-gate: `shelf:graph` is the only thing stopping a stale `dependsOn` (stale = fail-open); it is in `check`, but `moon run :test` alone skips it.

## Left behind

- Removed `~/.moon` (id, one 1.3 MB wasm plugin, temp) and `~/.proto` (an empty `temp/` moon created on first run). Neither existed before; both gone now.
- Worktree `agent-a6331229b8f5cdbca` is dirty, nothing committed: `.moon/`, `moon.yml`, `tools/moon_graph.py`, `packages/hello-ts/`, 52 `packages/*/moon.yml`, +1 line in root `pyproject.toml` (uv `exclude`), +1 line in the ignore file; `.moon/cache/` and `.venv/` ignored.
- Scratchpad: `clone/` (commits there only, own venv), `moonbin/` (npm install of moon 2.6.1), `m-*.log`, `mrun.sh`, `scen2.sh`, `seed.sh`.
- Untested: .NET package, coverage floor, Docker-container run, a `make check` baseline timed under the same load, why a Makefile edit re-ran lint (over-run, not under-run).

## The one command

`moon run :check` (from the repo root, after `uv sync`). Config: `.moon/workspace.yml`, `.moon/toolchains.yml`,
`.moon/tasks/all.yml`, `moon.yml`, `packages/*/moon.yml`, `tools/moon_graph.py`.
