# Changelog

## Unreleased

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
