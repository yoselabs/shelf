"""Scan for committed secrets with gitleaks, over only the code that changed.

Three scans: `staged` (the index, for a pre-commit hook), `range` (every commit since the upstream merge-base, plus the
uncommitted work: staged, unstaged and untracked; the gate's scan, like `any-gate changed`), `full` (all history, before a tag):
`scan_staged`, `scan_range`, `scan_full`.
A range with no upstream starts at the merge-base with the default branch (or, on the default branch itself, covers HEAD's own
history): never another branch's commits, since a shared git dir holds every sibling worktree's unpushed work. `full` is the only
scan of every ref. A finding names the file, line and rule and
never the secret (`--redact`). A missing scanner is an error, never a pass.

`python -m blueprint.secret_scan staged|range|full [--repo DIR]`; exit 1 on findings, 2 when the scan could not run.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_BASE = ("gitleaks", "--no-banner", "--no-color", "--redact", "--log-level", "error")


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


_DEFAULT_BRANCHES = ("origin/HEAD", "origin/main", "origin/master", "main", "master")


def _merge_base(repo: Path, env: Mapping[str, str] | None, other: str) -> str | None:
    found = _git(repo, env, "merge-base", "HEAD", other)
    return found.strip() or None if found else None


def _base(repo: Path, env: Mapping[str, str] | None) -> str | None:
    """The upstream merge-base, else the merge-base with the default branch (not HEAD's own branch); None when neither exists."""
    upstream = _merge_base(repo, env, "@{upstream}")
    if upstream:
        return upstream
    current = (_git(repo, env, "symbolic-ref", "--quiet", "--short", "HEAD") or "").strip()
    for name in _DEFAULT_BRANCHES:
        if name != current and (base := _merge_base(repo, env, name)):
            return base
    return None


def scan_staged(repo: Path, *, env: Mapping[str, str] | None = None) -> list[Leak]:
    """The findings in the index of `repo`, each once."""
    return _run(repo, env, ["git", "--pre-commit", "--staged"])


def scan_full(repo: Path, *, env: Mapping[str, str] | None = None) -> list[Leak]:
    """The findings in all history of `repo`, each once."""
    return _run(repo, env, ["git"])


def scan_range(repo: Path, *, env: Mapping[str, str] | None = None) -> list[Leak]:
    """The findings since the upstream (or default-branch) merge-base plus the uncommitted work; never another branch's commits."""
    base = _base(repo, env)
    leaks = _run(repo, env, ["git", "--log-opts", f"{base}..HEAD" if base else "HEAD"])
    leaks += scan_staged(repo, env=env)
    leaks += _run(repo, env, ["git", "--pre-commit"])
    leaks += _scan_untracked(repo, env)
    return sorted(set(leaks), key=lambda leak: (leak.file, leak.line, leak.rule))


def _scan_untracked(repo: Path, env: Mapping[str, str] | None) -> list[Leak]:
    """Every untracked, unignored file in one gitleaks process (one start per file is an antivirus scan per start)."""
    untracked = [p for p in (_git(repo, env, "ls-files", "-z", "--others", "--exclude-standard") or "").split("\0") if p]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        copied = 0
        for rel in untracked:
            source = repo / rel
            if not source.is_file() or source.is_symlink():
                continue
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            copied += 1
        if not copied:
            return []
        found = _run(repo, env, ["dir", str(root)])
    return [Leak(_relative(leak.file, root), leak.line, leak.rule) for leak in found]


def _relative(name: str, root: Path) -> str:
    path = Path(name)
    for base in (root, root.resolve()):
        if path.is_relative_to(base):
            return path.relative_to(base).as_posix()
    return name


_SCANS = {"staged": scan_staged, "range": scan_range, "full": scan_full}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m blueprint.secret_scan", description=__doc__)
    parser.add_argument("mode", choices=list(_SCANS))
    parser.add_argument("--repo", type=Path, default=Path())
    args = parser.parse_args(argv)
    try:
        leaks = _SCANS[args.mode](args.repo)
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
