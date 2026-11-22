"""`blueprint gate test`: the gate's tests through any-gate, with the repo's adapter runner.

One entry point, so a consumer's `test` recipe is one line. The shape is the gate kit's (any-gate's design.md): the adapter *plans*
(`path<TAB>key` per suite), the core (`any_gate test`) skips suites whose key already passed, queues for the test slot and calls the
adapter's *runner* with the rest. Both are run as subprocesses of the repo's own python (`sys.executable`), so blueprint depends on neither
package and a different core or adapter can take their place.

Python is the one adapter so far (`python -m any_gate_python`). It plans over a uv workspace (`packages/*`). A repo that is not one
declares its test units in `pyproject.toml` (`gate_units`): each unit's key hashes what its tests reach, so a change reruns only the
units it reaches. With `coverage` set, each unit's data is cached under its key and combined before the floor (`unit_runner`), so the
floor stays whole-repo while units are skipped. A repo that declares nothing runs its whole suite as one unit (`tests`, no key).
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from blueprint import gate_units, unit_runner

# Coverage is a whole-repo measure: a partial run cannot meet a floor, so the default run turns the plugin off (`just cov` measures).
DEFAULT_PYTEST_ARGS = "-p no:cov"

Execute = Callable[..., tuple[int, str]]


def whole_suite_plan() -> str:
    """The plan of a repo with no packages: its `tests` folder, with no key."""
    return "tests\t\n"


def is_workspace(repo: Path) -> bool:
    return any(repo.glob("packages/*/pyproject.toml"))


def cache_dir(repo: Path) -> Path:
    """Where unit coverage data is kept: `gate-coverage` in the git directory every worktree of `repo` shares."""
    done = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=repo, capture_output=True, text=True, check=False, timeout=60)
    shared = Path(done.stdout.strip()) if done.returncode == 0 and done.stdout.strip() else Path(".git")
    return unit_runner.worktree_cache((shared if shared.is_absolute() else repo / shared) / "gate-coverage", repo)


def commands(
    repo: Path, *, receipts: Path | None, lease_root: Path | None, pytest_args: str, cache: Path | None = None
) -> tuple[list[str] | None, list[str]]:
    """`(plan command or None, test command)`; the plan command's stdout is the test command's stdin."""
    py = sys.executable
    config = None if is_workspace(repo) else gate_units.load(repo)
    plan = [py, "-m", "any_gate_python", "plan", "--explain", "--plan"] if is_workspace(repo) else None
    test = [py, "-m", "any_gate", "test"]
    if receipts is not None:
        test += ["--receipts", str(receipts)]
    if lease_root is not None:
        test += ["--lease-root", str(lease_root)]
    if config is not None and config.coverage:
        where = cache or cache_dir(repo)
        test += ["--", py, "-m", "blueprint.unit_runner", "--repo", str(repo), "--cache", str(where), f"--pytest-args={pytest_args}"]
    else:
        pytest_args = shlex.join([*gate_units.read_config(repo).arguments(), *shlex.split(pytest_args)])
        test += ["--", py, "-m", "any_gate_python", "run", f"--pytest-args={pytest_args}"]
    return plan, test


def _execute(cmd: list[str], *, cwd: Path, stdin: str | None, env: dict[str, str]) -> tuple[int, str]:
    """Run `cmd`; return its exit code and, when it was the plan (no stdin to give), what it printed."""
    if stdin is None:
        done = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, text=True, check=False)
        return done.returncode, done.stdout
    return subprocess.run(cmd, cwd=cwd, env=env, input=stdin, text=True, check=False).returncode, ""


def run(
    repo: Path,
    *,
    env: dict[str, str],
    receipts: Path | None,
    lease_root: Path | None,
    pytest_args: str | None = None,
    execute: Execute = _execute,
    cache: Path | None = None,
) -> int:
    """Plan, then run what the plan names; the exit code of whichever failed first (a failed plan is never a pass).

    Pytest arguments default to turning the cov plugin off, except when the repo measures coverage, where they default to none.
    With a coverage floor the units' data is combined after a green run and the floor applied: the floor is whole-repo.
    """
    config = None if is_workspace(repo) else gate_units.load(repo)
    measuring = config is not None and bool(config.coverage)
    if config is not None:
        problems = list(config.problems)
        if config.units and (uncovered := gate_units.uncovered_test_folders(repo, config)):
            problems.append(f"test folders outside declared units: {', '.join(uncovered)}")
        if problems:
            sys.stderr.write("blueprint: " + "; ".join(problems) + "\n")
            return 2
    args = pytest_args if pytest_args is not None else ("" if measuring else DEFAULT_PYTEST_ARGS)
    filtered = bool(pytest_args and shlex.split(pytest_args))
    where = cache or cache_dir(repo)
    plan_cmd, test_cmd = commands(repo, receipts=receipts, lease_root=lease_root, pytest_args=args, cache=where)
    if config is not None:
        plan = gate_units.plan(repo, config, cached=unit_runner.cached(where, config, repo) if measuring and not filtered else None)
        if filtered:
            plan = "".join(f"{path}\t\n" for unit in config.units for path in unit.paths)
    elif plan_cmd is None:
        plan = whole_suite_plan()
    else:
        code, plan = execute(plan_cmd, cwd=repo, stdin=None, env=env)
        if code != 0:
            return code
    test_env = {**env, **gate_units.read_config(repo).env}
    code = execute(test_cmd, cwd=repo, stdin=plan, env=test_env)[0]
    if code != 0 or config is None or not measuring or filtered:
        return code
    return unit_runner.combine(repo, where, config)
