"""Scan for committed secrets with gitleaks, over only the code that changed.

Three modes: `staged` (the index, for a pre-commit hook), `range` (every commit since the upstream merge-base, plus the
uncommitted work: staged, unstaged and untracked; the gate's mode, like `any-gate changed`), `full` (all history, before a tag).
A range with no upstream is the full scan: run too much, never too little. A finding names the file, line and rule and
never the secret (`--redact`). A missing scanner is an error, never a pass.

`python -m blueprint.secret_scan staged|range|full [--repo DIR]`; exit 1 on findings, 2 when the scan could not run.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_BASE = ("gitleaks", "--no-banner", "--no-color", "--redact", "--log-level", "error")


class Mode(StrEnum):
    STAGED = "staged"
    RANGE = "range"
    FULL = "full"


class ScanError(RuntimeError):
    """The scan could not run (no scanner, a git or scanner failure); never to be read as clean."""


@dataclass(frozen=True)
class Leak:
    file: str
    line: int
    rule: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line} {self.rule}"


_GIT_TIMEOUT = 60
_GITLEAKS_TIMEOUT = 900


def _exec(argv: Sequence[str], repo: Path, env: Mapping[str, str] | None, timeout: int) -> subprocess.CompletedProcess[str]:
    """One child run; a hang or a missing program is a ScanError, never a clean scan."""
    try:
        return subprocess.run(argv, cwd=repo, env=env, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        hung = f"`{argv[0]}` timed out after {timeout}s"
        raise ScanError(hung) from error
    except FileNotFoundError as error:
        missing = f"{argv[0]} is not installed: run `just tools` (pinned in mise.toml)"
        raise ScanError(missing) from error


def _git(repo: Path, env: Mapping[str, str] | None, *args: str) -> str | None:
    done = _exec(["git", *args], repo, env, _GIT_TIMEOUT)
    return done.stdout if done.returncode == 0 else None


def _run(repo: Path, env: Mapping[str, str] | None, args: Sequence[str]) -> list[Leak]:
    """One gitleaks run; its JSON report holds the findings (exit 1 is "leaks found", anything else above 1 is a failure)."""
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        done = _exec([*_BASE, *args, "--report-format", "json", "--report-path", str(report)], repo, env, _GITLEAKS_TIMEOUT)
        if done.returncode not in (0, 1):
            failed = f"gitleaks failed ({done.returncode}): {done.stderr.strip()[:300]}"
            raise ScanError(failed)
        found: list[dict[str, object]] = json.loads(report.read_text(encoding="utf-8") or "[]") if report.exists() else []
    return [Leak(str(f["File"]), int(str(f["StartLine"])), str(f["RuleID"])) for f in found]


def _base(repo: Path, env: Mapping[str, str] | None) -> str | None:
    found = _git(repo, env, "merge-base", "HEAD", "@{upstream}")
    return found.strip() or None if found else None


def scan(repo: Path, mode: Mode, *, env: Mapping[str, str] | None = None) -> list[Leak]:
    """The findings of `mode` over `repo`, each once."""
    if mode is Mode.STAGED:
        return _run(repo, env, ["git", "--pre-commit", "--staged"])
    base = _base(repo, env) if mode is Mode.RANGE else None
    if base is None:
        return _run(repo, env, ["git"])
    leaks = _run(repo, env, ["git", "--log-opts", f"{base}..HEAD"])
    leaks += _run(repo, env, ["git", "--pre-commit", "--staged"])
    leaks += _run(repo, env, ["git", "--pre-commit"])
    untracked = (_git(repo, env, "ls-files", "-z", "--others", "--exclude-standard") or "").split("\0")
    for rel in filter(None, untracked):
        leaks += _run(repo, env, ["dir", rel])
    return sorted(set(leaks), key=lambda leak: (leak.file, leak.line, leak.rule))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m blueprint.secret_scan", description=__doc__)
    parser.add_argument("mode", choices=[m.value for m in Mode])
    parser.add_argument("--repo", type=Path, default=Path())
    args = parser.parse_args(argv)
    try:
        leaks = scan(args.repo, Mode(args.mode))
    except ScanError as error:
        sys.stderr.write(f"secret scan: {error}\n")
        return 2
    for leak in leaks:
        sys.stderr.write(f"secret scan: {leak}\n")
    if leaks:
        sys.stderr.write("secret scan: rotate what leaked (it is in git history once committed); a false positive goes in .gitleaks.toml\n")
    return 1 if leaks else 0


if __name__ == "__main__":
    raise SystemExit(main())
