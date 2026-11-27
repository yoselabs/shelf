# Changelog

## 0.15.0

- The gate has fewer steps. `blueprint` now runs the commit guard, the linter preset check, the render check and the audit in one process (`blueprint gate blueprint`); `lint-changed` (and `lint`) also run codespell; the standard list drops `guard`, `preset`, `render` and `spell-changed` (their recipes stay for hooks and humans). A consumer's `gate-inputs.toml` keys for dropped steps match nothing (an unkeyed step always runs); re-key `lint-changed` to `*` and `blueprint` to `*`. `gate.runs-blueprint` accepts `blueprint gate blueprint`; the python-uv spelling row accepts `blueprint gate lint`. Corpus diff against 0.14.2: no `passing -> failing`; the moves are the linter/tests rows below and `gate.wide-inputs-have-a-reason` on a2kay (absent -> failing: its six `*` steps need `[wide]` entries).
- The steps runner (any-gate 0.5.0): SIGTERM and SIGHUP stop every step's tree; a step the gate stopped is a flag, not exit 125; a crashed step is a failed step; `GATE_FAIL_FAST`; a clean tree no gate has passed runs every declared step once.

- `gate.wide-inputs-have-a-reason` (new, warns until the next audit): a step declared `["*"]` in gate-inputs.toml needs a `[wide]` entry `<step> = "<kind>: <why>"`, kind one of change-set, self-keyed, reads-everything, outside-files. It does not guess what a recipe reads.
- The audit reads the justfile once per run (a2kay: 30 processes and 2.4 s became 20 and 1.8 s); the steps runner shows a failure as it lands and takes `--fail-fast` and `--step-limit` (any-gate 0.4.0).

- Test doubles: `Repo.env` drops the developer's `BLUEPRINT_TIMEOUT`, and `gate_py._lease_installed` is the one seam where the machine's `any_lease` changes the release run's command (both shapes tested).

- `agents.worktrees-in-sync` ignores the age of unmerged work while prek runs the pre-push hooks (`PRE_COMMIT_TO_REF` set): the push is the step that lands it, and the row used to refuse that push. Being behind main still fails. An ordinary audit is unchanged.

- `[tool.blueprint.test] randomize = true`: `blueprint gate test-all` (the release run) passes `-p randomly`; `check` does not. The repo keeps `-p no:randomly` in `addopts`.

- python-uv `tests` row also requires `filterwarnings` in `pyproject.toml` (`["error", ...]`: a leaked process, file or stream fails the test that made it). The `linter` row requires the bandit (`S`) and complexity (`C90`) rules, by name or through `ALL`. Both warn until the next audit (ADR 0018). Corpus diff against 0.14.2: 7 of 42 repos move to not set up (a2kay tests; a2skill, a2web, iorlas-task-loop, mcp-gateway, mempalace, yosefactory linter).

## 0.14.2

- Snapshot also carries any-gate (the test-slot waiter names a hung holder's pid and age, repeats every 5 minutes) and the any-knowledge `working-with-agents` template (delivery scope for multi-ticket work).

- `blueprint check --brief` (what `just blueprint` prints) clips evidence to 200 and the fix to 240 characters, and says when it cut; the full text stays in `blueprint check`. A not-set-up standard row was ~1 KB each.

- Dead code removed (`LAYERS`, `OUTCOMES`, `_LINT_BEAD`, `CALLS_ID`); `render` uses `gate_graph.JUSTFILES`. No behaviour change.
- python-uv `tests` row also requires `--strict-markers` in pytest `addopts` (a marker typo fails instead of selecting nothing). New row: warns until the next audit (ADR 0018).
- `blueprint.testing`: `run_cli` runs the engine in-process (no interpreter start per call); `Repo.git` turns commit and tag signing off so a developer's global config cannot hang a throwaway repo.
- `hooks.pre-push-is-the-gate` accepts a `git lfs push` hook (prek replaces LFS's own pre-push hook) and a hook that runs a `bash <script>.sh` whose script runs `just check`.
- `gate.no-ci` takes a per-workflow `[[override]] id = "gate.no-ci"` (scope, reason, expiry): no CI stays the default, a repo that needs one says so (ADR 0027 amended).

## 0.14.1

- Version files corrected: tag `blueprint-v0.14.0` was cut on a commit whose `pyproject.toml` still said 0.13.2 (0.13.1 and 0.13.2 had been released meanwhile). The code in `blueprint-v0.14.0` is the 0.14.0 content below; pin `blueprint-v0.14.1`, which carries it with the right version.

- The mcp framework rows (`build`, `tests`, `surface-integrity`) accept `blueprint gate test` as running pytest, so a repo on the standard rendered test step no longer fails them.

## 0.14.0

- **A comment or a message naming a tool no longer counts as running it**: the gate text the stack rows read drops comment lines and the text of `echo`/`printf` lines (a command chained after them still counts). Before, `# ruff check .` or `echo "docker build -f Dockerfile ."` passed the linter and Dockerfile-tests rows.
- `stack.roles` version 5: the python-uv `tests` role also needs `pytest-timeout` in the dependencies and `timeout = <seconds>` in `[tool.pytest.ini_options]` (a hung test fails the run; no repository has CI to kill it). It warns until the next audit (ADR 0018).
- Editor and interpreter litter (`.DS_Store`, `.pyc`, `.swp`) beside reached code no longer changes a test unit's key. The rendered `deps` recipe hands package folders to `xargs` NUL-separated.
- `agents.worktrees-in-sync` and `agents.other-worktrees` compare against `origin/main` when it exists (a clone's local `main` goes stale beside worktrees), else `main`.
- `lint` and `spell` (whole-repo linters) render without `release-gate`; only the release recipes are opt-in.
- Units under `pytest-cov` run with `--cov-fail-under=0`: the floor is applied once, to the combined data.
## 0.13.2

- Snapshot only, no blueprint change: carries git-porcelain 0.31.0 (`take_branch`/`restart_branch` `track=`, `BranchTaken.upstream`).

## 0.13.1

- Snapshot only, no blueprint change: carries any-agent 0.23.0 (`Harness.effort_levels`, `Summary.res["tokens"]["reasoning"]`).

## 0.13.0

- Node coverage floors and alternatives are judged in the node project's folder (`ui/`), not the repo root; the coverage config accepts any `vitest.config.*` extension.
- Python stack rows recognize pinned Ruff commands through `uv tool run` and `uvx`; mixed-stack tests verify `node-tooling` edges.
- Gate tests refuse invalid or unowned units; CLI-filtered runs cannot populate plain-run coverage caches. Keys include external test
  configuration and test package initializers. Recipe checks resolve imported/defaulted recipes and quoted or continued calls; Node
  installs use the detected folder and its lockfile. Lint preserves the first failure, including signal exits, while running both tools.
- Release recipes render only with `[tool.blueprint.gate] release-gate = true`; measured test units can enforce their floor inside `check`.
- Rendered `tools` installs Node dependencies after mise in the detected folder, using npm, pnpm or yarn only with its lockfile.
- `[tool.blueprint.test]` `pytest-args`, `marks` and `env` configure every test run and invalidate every unit's cached key.
- The `python-uv` stack accepts `ruff.toml` / `.ruff.toml` and `pyrefly.toml`, preserving lint-table and strict-preset requirements.
- `gate test-all` uses `[tool.coverage.report] fail_under` when `[tool.blueprint.test] floor` is unset, before falling back to 65.
- **Test units for a repo that is not a workspace**: `[tool.blueprint.test]` units, keys from the import graph, per-unit coverage data cached and combined before the floor (`coverage run` or pytest-cov). `gate_test.run`'s `pytest_args` defaults to none with coverage.
- New rows: `gate.recipe-shadowing`, `gate.recipe-calls`, `agents.other-worktrees` (audit-only). `agents.worktrees-in-sync` (version 2) judges this worktree only.
- New stack `node-tooling` for a build-tool-only `package.json`.
- **The python steps are engine commands**: `blueprint gate lint|format|spell|test-all`, with `lint-changed` and `spell-changed` in `check`; a repo's paths, extra steps and floor are data in `[tool.blueprint.gate]` and `[tool.blueprint.test]`, so it defines no recipe of its own. `check-all` runs `check-extra`. `stack.roles` is version 4.
- `stack.dockerfile.tests` needs a `docker build` line naming the path (`--check` counts). `gate.clean-clone` shows the failing step and 20 lines of its log. See ADR 0033.

## 0.12.0

- `blueprint` opts in to the public-`Any` rule: each remaining `Any` in a public signature is parsed TOML and says so. `check_dockerfile_pins` and `testing` bound their git calls with `timeout=` (a git timeout in the recipe falls back to the file walk).

## 0.11.0

- `gate.clean-clone` points mise at the injected env's `HOME` (`$HOME/.config/mise`), not the process home.

## 0.10.0

- **Breaking: `secret_scan.scan(repo, mode)` and `Mode` are gone.** `scan_staged(repo)`, `scan_range(repo)` and `scan_full(repo)` are the three scans; `python -m blueprint.secret_scan staged|range|full` is unchanged.
- `stack.shelf-sources` fails mixed shelf tags/spellings and re-pinning overrides; `init` normalizes them.
- Gate steps declare their inputs (`gate-inputs.toml`); an unaffected step is not started; new `gate.step-inputs` audit row. `stack.agent-cli-pins` added.
- The knowledge, ADR and agent-docs checks moved to the `any-knowledge` package.

## 0.8.0

- **Breaking: `runner.run` lost its `audit` flag.** `run(...)` is the per-commit gate, `run_audit(...)` also runs the audit-only checks (the CLI picks one by `--audit`). What is checked and rendered is unchanged.
- **Breaking: `report.write` lost its `prune` flag.** `write(...)` prunes the reports of a concern the run no longer has, `write_concern(...)` (a one-concern run) leaves the others. Written files are unchanged.
- Test helper `Repo.write(..., executable=True)` is now `Repo.write_executable(...)`.
- Every text read and write carries `encoding="utf-8"`; every `errors="replace"` carries a `# lossy-ok:` marker; globs that feed output are wrapped in `sorted()`. No output changes on a UTF-8 machine.
- `secret_scan` and `guard`: every child process has a timeout (a hang is `ScanError`, or exit 2 for the guard, never a pass); `secret_scan` no longer reads `os.environ` or calls `shutil.which` (a missing gitleaks is the same `ScanError` message).
- Left alone on purpose: the engine is stdlib only (it runs from a bare clone on `PYTHONPATH`, README), so it does not use stream-proc, child-env, content-digest or any-clock.
