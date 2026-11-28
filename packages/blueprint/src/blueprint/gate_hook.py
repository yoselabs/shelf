"""The commit hook, one process: `blueprint gate hook`.

Five hooks each started `uv run` (secret scan, guard, preset drift, ruff check, ruff format): five interpreter starts a commit, on a
machine where every file open is slow. One entry runs the same checks over the staged files, in order, and returns the worst exit code.
Every check still runs after one fails, so a commit shows everything to fix at once.

| check | judges | when |
|---|---|---|
| secret scan | the index | always |
| guard | the staged pyproject.toml | always (a clean pass when none is staged) |
| preset drift | the repo's lint config | only when pyproject.toml is staged |
| ruff check, ruff format --check | staged `.py` under `lint-paths` (none set: all) | when one is staged |

A git failure reading the index fails the hook (exit 2): a hook that cannot see the staged files must not pass. With no `lint-paths`
every staged `.py` is linted, so the hook may refuse a scratch file the gate does not lint: set `lint-paths` to narrow both alike.
"""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

from blueprint import gate_py, guard, preset, secret_scan

if TYPE_CHECKING:
    from pathlib import Path

_GIT_TIMEOUT = 60
_RUFF_TIMEOUT = 600


def _staged(repo: Path) -> list[str]:
    """Paths added, copied, modified or renamed in the index (never a deleted one); raises `_GitFailedError`."""
    done = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=_GIT_TIMEOUT,
    )
    if done.returncode != 0:
        raise secret_scan.ScanError(done.stderr.strip() or f"exit {done.returncode}")
    return [p for p in done.stdout.split("\0") if p]


def _under(path: str, roots: list[str]) -> bool:
    return gate_py.under(path, roots)


def _secrets(repo: Path) -> int:
    try:
        leaks = secret_scan.scan_staged(repo)
    except secret_scan.ScanError as error:
        sys.stderr.write(f"secret scan: {error}\n")
        return 2
    for leak in leaks:
        sys.stderr.write(f"secret scan: {leak}\n")
    if leaks:
        sys.stderr.write("secret scan: rotate what leaked (it is in git history once committed); a false positive goes in .gitleaks.toml\n")
    return 1 if leaks else 0


def _run_ruff(repo: Path, files: list[str]) -> int:
    code = 0
    for args in (["check"], ["format", "--check"]):
        done = subprocess.run(
            [sys.executable, "-m", "ruff", *args, "--force-exclude", *files],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
            timeout=_RUFF_TIMEOUT,
        )
        sys.stdout.write(done.stdout)
        sys.stderr.write(done.stderr)
        code = max(code, done.returncode)
    return code


def run(repo: Path) -> int:
    """The worst exit code of the checks the staged files call for."""
    try:
        staged = _staged(repo)
    except (secret_scan.ScanError, OSError, subprocess.SubprocessError) as error:
        sys.stderr.write(f"hook: git diff --cached failed ({error}): the staged files are unknown, so the commit is refused\n")
        return 2
    codes = [_secrets(repo), guard.check(committed=False)]
    if "pyproject.toml" in staged:
        codes.append(preset.check(repo))
    roots = gate_py.settings(repo).get("gate", {}).get("lint-paths", [])
    python = [p for p in staged if p.endswith(".py") and _under(p, [str(r) for r in roots])]
    if python:
        codes.append(_run_ruff(repo, python))
    return max(codes)
