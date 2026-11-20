"""`blueprint gate test`: the gate's tests through any-gate, with the repo's adapter runner.

One entry point, so a consumer's `test` recipe is one line. The shape is the gate kit's (any-gate's design.md): the adapter *plans*
(`path<TAB>key` per suite), the core (`any_gate test`) skips suites whose key already passed, queues for the test slot and calls the
adapter's *runner* with the rest. Both are run as subprocesses of the repo's own python (`sys.executable`), so blueprint depends on neither
package and a different core or adapter can take their place.

Python is the one adapter so far (`python -m any_gate_python`). It plans over a uv workspace (`packages/*`); a repo that is not one runs
its whole suite as one unit (`tests`, no key, so never skipped).
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# Coverage is a whole-repo measure: a partial run cannot meet a floor, so the default run turns the plugin off (`just cov` measures).
DEFAULT_PYTEST_ARGS = "-p no:cov"

Execute = Callable[..., tuple[int, str]]


def whole_suite_plan() -> str:
    """The plan of a repo with no packages: its `tests` folder, with no key."""
    return "tests\t\n"


def is_workspace(repo: Path) -> bool:
    return any(repo.glob("packages/*/pyproject.toml"))


def commands(repo: Path, *, receipts: Path | None, lease_root: Path | None, pytest_args: str) -> tuple[list[str] | None, list[str]]:
    """`(plan command or None, test command)`; the plan command's stdout is the test command's stdin."""
    py = sys.executable
    plan = [py, "-m", "any_gate_python", "plan", "--explain", "--plan"] if is_workspace(repo) else None
    test = [py, "-m", "any_gate", "test"]
    if receipts is not None:
        test += ["--receipts", str(receipts)]
    if lease_root is not None:
        test += ["--lease-root", str(lease_root)]
    test += ["--", py, "-m", "any_gate_python", "run", f"--pytest-args={pytest_args}"]
    return plan, test


def _execute(cmd: list[str], *, cwd: Path, stdin: str | None) -> tuple[int, str]:
    """Run `cmd`; return its exit code and, when it was the plan (no stdin to give), what it printed."""
    if stdin is None:
        done = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, text=True, check=False)
        return done.returncode, done.stdout
    return subprocess.run(cmd, cwd=cwd, input=stdin, text=True, check=False).returncode, ""


def run(
    repo: Path, *, receipts: Path | None, lease_root: Path | None, pytest_args: str = DEFAULT_PYTEST_ARGS, execute: Execute = _execute
) -> int:
    """Plan, then run what the plan names; the exit code of whichever failed first (a failed plan is never a pass)."""
    plan_cmd, test_cmd = commands(repo, receipts=receipts, lease_root=lease_root, pytest_args=pytest_args)
    if plan_cmd is None:
        plan = whole_suite_plan()
    else:
        code, plan = execute(plan_cmd, cwd=repo, stdin=None)
        if code != 0:
            return code
    return execute(test_cmd, cwd=repo, stdin=plan)[0]
