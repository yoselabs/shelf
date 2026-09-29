"""The git process runner and repo state (status, ahead/behind, merge state).

The package docstring (``git_porcelain``) states the contract: the real git binary,
no prompts, fail loud with :class:`GitError`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from git_porcelain.errors import GitError

if TYPE_CHECKING:
    from collections.abc import Mapping

_GIT = "git"


def _git_env() -> dict[str, str]:
    """Child env that fails loud instead of prompting for credentials."""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    return env


def _run(vault: Path, args: tuple[str, ...], env: Mapping[str, str] | None, timeout: float | None) -> subprocess.CompletedProcess[str]:
    if shutil.which(_GIT) is None:
        msg = "git not found on PATH"
        raise GitError(msg, retryable=False, hint="install git")
    try:
        return subprocess.run(
            [_GIT, "-C", str(vault), *args],
            check=False,
            capture_output=True,
            text=True,
            env={**_git_env(), **(env or {})},
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        msg = f"git {args[0] if args else ''} timed out after {timeout}s"
        raise GitError(msg, retryable=True) from exc
    except OSError as exc:  # pragma: no cover - exec failure
        msg = f"failed to invoke git: {exc}"
        raise GitError(msg, retryable=False) from exc


def run_git(
    vault: Path,
    *args: str,
    check: bool = True,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
) -> str:
    """Run ``git -C <vault> <args>`` fail-loud; return stdout.

    ``env`` adds variables for this call only (an author identity, say). ``timeout``
    bounds a network call; running out raises a retryable :class:`GitError`.
    """
    proc = _run(vault, args, env, timeout)
    if check and proc.returncode != 0:
        msg = f"git {args[0] if args else ''} exited {proc.returncode}: {proc.stderr.strip()[:300]}"
        raise GitError(msg, retryable=False)
    return proc.stdout


def git_returncode(vault: Path, *args: str) -> int:
    """Run a git command whose answer is its exit code (``merge-base --is-ancestor``)."""
    return _run(vault, args, None, None).returncode


def is_repo(vault: Path) -> bool:
    """Return True if ``vault`` is inside a git work tree (False if git is missing)."""
    if shutil.which(_GIT) is None:
        return False
    out = run_git(vault, "rev-parse", "--is-inside-work-tree", check=False).strip()
    return out == "true"


def has_upstream(vault: Path) -> bool:
    """Return True if the current branch has an upstream tracking branch configured."""
    out = run_git(vault, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}", check=False)
    return bool(out.strip()) and "fatal" not in out.lower()


def merge_in_progress(vault: Path) -> bool:
    """Return True if a merge is in progress (a ``MERGE_HEAD`` exists in the git dir)."""
    git_dir = run_git(vault, "rev-parse", "--git-dir", check=False).strip()
    if not git_dir:
        return False
    base = Path(git_dir)
    merge_head = (base if base.is_absolute() else vault / base) / "MERGE_HEAD"
    return merge_head.exists()


def sync_status(vault: Path) -> dict[str, Any]:
    """Branch / clean / changed count / ahead-behind / merge-in-progress (no network)."""
    branch = run_git(vault, "rev-parse", "--abbrev-ref", "HEAD", check=False).strip() or "HEAD"
    porcelain = run_git(vault, "status", "--porcelain", check=False).strip()
    changed = len([ln for ln in porcelain.splitlines() if ln.strip()])
    ahead = behind = 0
    if has_upstream(vault):
        counts = run_git(vault, "rev-list", "--left-right", "--count", "@{upstream}...HEAD", check=False).split()
        if len(counts) == 2:
            behind, ahead = int(counts[0]), int(counts[1])
    return {
        "branch": branch,
        "clean": changed == 0,
        "changed_files": changed,
        "ahead": ahead,
        "behind": behind,
        "conflict_paused": merge_in_progress(vault),
    }


def readiness(vault: Path, *, check_push: bool = True) -> dict[str, Any]:
    """Is git usable here? (repo / identity / remote / push access). Never raises.

    ``check_push=False`` skips the network ``ls-remote`` probe — used by ``intro``,
    which must stay local/fast; ``push_access`` is then reported as ``None``.
    """
    if not is_repo(vault):
        return {"is_repo": False, "identity": False, "remote": False, "push_access": False}
    email = run_git(vault, "config", "user.email", check=False).strip()
    remote = run_git(vault, "remote", check=False).strip()
    push_access: bool | None = None
    if check_push and remote:
        try:
            run_git(vault, "ls-remote", "--exit-code", check=True)
            push_access = True
        except GitError:
            push_access = False
    return {"is_repo": True, "identity": bool(email), "remote": bool(remote), "push_access": push_access}


def unmerged_paths(vault: Path) -> list[str]:
    """Return the repo-relative paths that are currently unmerged (conflicted)."""
    out = run_git(vault, "diff", "--name-only", "--diff-filter=U", check=False)
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def has_conflict_markers(path: Path) -> bool:
    """Return True if ``path`` contains git conflict markers (unreadable files are False)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return "<<<<<<<" in text and ">>>>>>>" in text


def show_stage(vault: Path, stage: int, rel: str) -> str:
    """The clean blob for an index stage (1 base, 2 ours, 3 theirs); '' if absent."""
    return run_git(vault, "show", f":{stage}:{rel}", check=False)


def dirty_rels(vault: Path) -> list[str]:
    """Return the repo-relative paths of all changed and untracked files, unquoted.

    Each untracked FILE is listed (git otherwise collapses an untracked directory), and a
    rename lists its new path.
    """
    return [entry.path for entry in status(vault)]


@dataclass(frozen=True)
class StatusEntry:
    """One line of ``git status``: the two-letter code, the path, and the origin of a rename."""

    code: str
    path: str
    orig_path: str | None = None

    @property
    def tracked(self) -> bool:
        """False for an untracked or ignored path; True when git already knows it."""
        return self.code not in {"??", "!!"}


def status(vault: Path) -> list[StatusEntry]:
    """Every changed, staged and untracked path, one entry per file, paths unquoted."""
    fields = run_git(vault, "status", "--porcelain=v1", "-z", "-uall", check=False).split("\0")
    entries: list[StatusEntry] = []
    i = 0
    while i < len(fields):
        item = fields[i]
        i += 1
        if len(item) < 4:
            continue
        code, orig = item[:2], None
        if "R" in code or "C" in code:
            orig = fields[i]
            i += 1
        entries.append(StatusEntry(code=code, path=item[3:], orig_path=orig))
    return entries
