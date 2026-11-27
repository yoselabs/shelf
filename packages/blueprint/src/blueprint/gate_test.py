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

import json
import shlex
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from blueprint import gate_py, gate_units, unit_runner

# Coverage is a whole-repo measure: a partial run cannot meet a floor, so the default run turns the plugin off (`just cov` measures).
DEFAULT_PYTEST_ARGS = "-p no:cov"

Execute = Callable[..., tuple[int, str]]


def whole_suite_plan() -> str:
    """The plan of a repo with no packages: its `tests` folder, with no key."""
    return "tests\t\n"


def is_workspace(repo: Path) -> bool:
    return any(repo.glob("packages/*/pyproject.toml"))


def shared_git_dir(repo: Path) -> Path:
    """The git directory every worktree of `repo` shares."""
    done = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=repo, capture_output=True, text=True, check=False, timeout=60)
    shared = Path(done.stdout.strip()) if done.returncode == 0 and done.stdout.strip() else Path(".git")
    return shared if shared.is_absolute() else repo / shared


def cache_dir(repo: Path) -> Path:
    """Where unit coverage data is kept: `gate-coverage` in the git directory every worktree of `repo` shares."""
    return unit_runner.worktree_cache(shared_git_dir(repo) / "gate-coverage", repo)


def slow_receipts(repo: Path, receipts: Path | None) -> Path:
    """Where a suite's slow-green keys are kept: beside the normal receipts, so a green per-commit run never stands for them."""
    return receipts.with_name(f"slow-{receipts.name}") if receipts is not None else shared_git_dir(repo) / "gate-receipts-slow.json"


def leaves_slow_out(repo: Path) -> bool:
    """Whether the per-commit run's `marks` exclude `slow` (`not slow`): then a suite's slow tests have a pass of their own."""
    return "notslow" in gate_units.read_config(repo).marks.replace(" ", "")


def commands(
    repo: Path,
    *,
    receipts: Path | None,
    lease_root: Path | None,
    pytest_args: str,
    whole: bool,
    cache: Path | None = None,
    unit_keys: dict[str, str] | None = None,
    only: str = "",
) -> tuple[list[str] | None, list[str]]:
    """`(plan command or None, test command)`; the plan command's stdout is the test command's stdin.

    `whole` is the release run (`test-all`): the plan lists every suite and the runner runs every mark.
    `only` runs just that mark expression (the slow pass of `check`), whatever the configured `marks`.
    """
    py = sys.executable
    config = None if is_workspace(repo) else gate_units.load(repo)
    plan = [py, "-m", "any_gate_python", "plan", "--explain", "--plan", *(["--all"] if whole else [])] if is_workspace(repo) else None
    test = [py, "-m", "any_gate", "test"]
    if receipts is not None:
        test += ["--receipts", str(receipts)]
    if lease_root is not None:
        test += ["--lease-root", str(lease_root)]
    if config is not None and config.coverage:
        where = cache or cache_dir(repo)
        runner = [py, "-m", "blueprint.unit_runner", "--repo", str(repo), "--cache", str(where), f"--pytest-args={pytest_args}"]
        given = [f"--keys={json.dumps(unit_keys, sort_keys=True)}"] if unit_keys is not None else []
        test += ["--", *runner, *given, *(["--whole"] if whole else []), *([f"--only={only}"] if only else [])]
    else:
        settings = gate_units.read_config(repo)
        base = settings.every_mark() if whole or only else settings.arguments()
        pytest_args = shlex.join([*base, *(["-m", only] if only else []), *shlex.split(pytest_args)])
        test += ["--", py, "-m", "any_gate_python", "run", f"--pytest-args={pytest_args}"]
    return plan, test


def _execute(cmd: list[str], *, cwd: Path, stdin: str | None, env: dict[str, str]) -> tuple[int, str]:
    """Run `cmd`; return its exit code and, when it was the plan (no stdin to give), what it printed."""
    if stdin is None:
        done = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, text=True, check=False)
        return done.returncode, done.stdout
    return subprocess.run(cmd, cwd=cwd, env=env, input=stdin, text=True, check=False).returncode, ""


def declared_floor(repo: Path) -> float | None:
    """The whole-repo floor the repo declares (`[tool.blueprint.test] floor`, else `[tool.coverage.report] fail_under`), or None."""
    config = gate_py.settings(repo)
    for raw in (config.get("test", {}).get("floor"), config.get("coverage-report", {}).get("fail_under")):
        if isinstance(raw, int | float) and not isinstance(raw, bool):
            return float(raw)
    return None


def _cov_off(repo: Path, extra: str) -> bool:
    """Whether the repo's pytest arguments (or this call's) turn the cov plugin off (`-p no:cov`): pytest then rejects `--cov`."""
    words = [*gate_units.read_config(repo).pytest_args, *shlex.split(extra)]
    return any(a == "-pno:cov" or (a == "no:cov" and i > 0 and words[i - 1] == "-p") for i, a in enumerate(words))


def run(
    repo: Path,
    *,
    env: dict[str, str],
    receipts: Path | None,
    lease_root: Path | None,
    pytest_args: str | None = None,
    whole: bool,
    execute: Execute = _execute,
    cache: Path | None = None,
) -> int:
    """Plan, then run what the plan names; the exit code of whichever failed first (a failed plan is never a pass).

    Pytest arguments default to turning the cov plugin off, except when the repo measures coverage, where they default to none.
    With a coverage floor the units' data is combined after a green run and the floor applied: the floor is whole-repo.

    `whole` is `test-all`, the release run: the same runner and plan as `test`, with every suite planned, no key (a receipt is neither
    read nor written), every mark run, and `randomize` honoured. A floor is judged only when the repo declares one and the run is not an
    override (pytest arguments given); a repo without `coverage` mode is measured by pytest-cov across the stages, one report at the end.
    """
    config = None if is_workspace(repo) else gate_units.load(repo)
    measuring = config is not None and bool(config.coverage)
    if config is not None and (problems := _problems(repo, config)):
        sys.stderr.write("blueprint: " + "; ".join(problems) + "\n")
        return 2
    filtered = bool(pytest_args and shlex.split(pytest_args))
    args, floor = _arguments(repo, pytest_args, whole=whole, measuring=measuring)
    where = cache or cache_dir(repo)
    blank = filtered or whole
    unit_keys = gate_units.keys(repo, config) if config is not None and (measuring or not blank) else None  # once per run
    plan_cmd, test_cmd = commands(
        repo, receipts=receipts, lease_root=lease_root, pytest_args=args, cache=where, whole=whole, unit_keys=unit_keys
    )  # pytest arguments, or the release run: no key, so no receipt a later normal run could skip on
    if config is not None:
        cached = unit_runner.cached(where, config, unit_keys or {}) if measuring and not blank else None
        plan = (
            "".join(f"{path}\t\n" for unit in config.units for path in unit.paths)
            if blank
            else gate_units.plan(repo, config, cached=cached, unit_keys=unit_keys)
        )
    elif plan_cmd is None:
        plan = whole_suite_plan()
    else:
        code, plan = execute(plan_cmd, cwd=repo, stdin=None, env=env)
        if code != 0:
            return code
        if blank:
            plan = "".join(f"{line.split(chr(9))[0]}\t\n" for line in plan.splitlines() if line)
    test_env = {**env, **gate_units.read_config(repo).env}
    with tempfile.TemporaryDirectory() as tmp:
        if floor is not None:
            test_env["COVERAGE_FILE"] = str(Path(tmp) / "data")
        code = execute(test_cmd, cwd=repo, stdin=plan, env=test_env)[0]
        if code == 0 and not blank and leaves_slow_out(repo) and (slow_plan := _slow_plan(repo, config, plan, unit_keys)):
            slow = commands(
                repo,
                receipts=slow_receipts(repo, receipts),
                lease_root=lease_root,
                pytest_args="",
                cache=where,
                whole=False,
                unit_keys=unit_keys,
                only="slow",
            )[1]
            code = execute(slow, cwd=repo, stdin=slow_plan, env=test_env)[0]
        if code == 0 and floor is not None:
            report = [sys.executable, "-m", "coverage", "report", "--show-missing", f"--fail-under={floor:g}"]
            code = execute(report, cwd=repo, stdin="", env=test_env)[0]
    judged = config is not None and measuring and not filtered and declared_floor(repo) is not None
    if code != 0 or not judged or config is None:
        return code  # without a floor nothing is judged from the combined data
    return unit_runner.combine(repo, where, config, unit_keys)


def _slow_plan(repo: Path, config: gate_units.Config | None, plan: str, unit_keys: dict[str, str] | None) -> str:
    """The suites whose slow tests the per-commit run left out, each with its key (any-gate skips one whose key is already slow-green).

    Empty for a repo whose suites have no key (a bare `tests` folder): nothing says what changed, so only `check-all` runs them.
    """
    if config is not None:
        return gate_units.plan(repo, config, cached=None, unit_keys=unit_keys)
    return plan if any(line.split("\t")[1:2] not in ([], [""]) for line in plan.splitlines()) else ""


def _problems(repo: Path, config: gate_units.Config) -> list[str]:
    problems = list(config.problems)
    if config.units and (uncovered := gate_units.uncovered_test_folders(repo, config)):
        problems.append(f"test folders outside declared units: {', '.join(uncovered)}")
    return problems


def _arguments(repo: Path, pytest_args: str | None, *, whole: bool, measuring: bool) -> tuple[str, float | None]:
    """`(the pytest arguments for every stage, the floor to judge afterwards or None)`."""
    given = pytest_args or ""
    floor = declared_floor(repo) if whole and not measuring and not shlex.split(given) else None
    if floor is not None and _cov_off(repo, given):
        message = f'floor {floor:g} not judged: pytest-args turn the cov plugin off; set coverage = "coverage" to measure it'
        sys.stderr.write(f"blueprint: {message}\n")
        floor = None
    own: list[str] = []
    if whole and gate_py.settings(repo).get("test", {}).get("randomize") is True:
        own += ["-p", "randomly"]  # the release run shuffles; `check` does not
    if floor is not None:
        own += ["--cov", "--cov-append", "--cov-report=", "--cov-fail-under=0"]  # one stage cannot meet a whole-repo floor
    default = "" if measuring or floor is not None else DEFAULT_PYTEST_ARGS
    return shlex.join([*own, *shlex.split(pytest_args if pytest_args is not None else default)]), floor
