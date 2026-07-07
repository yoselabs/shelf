"""git-porcelain — a pure, fail-loud git surface over the git binary.

One place to shell out to git. Every function takes a repo path (and git args) and
returns git data: repo state, porcelain status, ahead/behind, index-stage blobs. It
knows nothing about any host's domain model — a caller maps that git data onto its own
concerns.

We shell to the real git binary rather than adopt a library (pygit2/dulwich bypass the
user's credential helper + SSH agent; GitPython is a maintenance-mode subprocess wrapper
that hangs on credential-helper repos). The binary is the reference implementation the
user already configured; the only hardening is `GIT_TERMINAL_PROMPT=0` (fail loud instead
of hanging on a credential prompt) and `GIT_SSH_COMMAND=BatchMode` — the git-fidelity
contract, deliberately kept here. Failures raise :class:`GitError`; a host translates it
into its own error type at the seam.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from git_porcelain.errors import GitError

_GIT = "git"


def _git_env() -> dict[str, str]:
    """Child env that fails loud instead of prompting for credentials."""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    return env


def run_git(vault: Path, *args: str, check: bool = True) -> str:
    """Run ``git -C <vault> <args>`` fail-loud; return stdout."""
    if shutil.which(_GIT) is None:
        msg = "git not found on PATH"
        raise GitError(msg, retryable=False, hint="install git or disable sync")
    try:
        proc = subprocess.run(
            [_GIT, "-C", str(vault), *args],
            check=False,
            capture_output=True,
            text=True,
            env=_git_env(),
        )
    except OSError as exc:  # pragma: no cover - exec failure
        msg = f"failed to invoke git: {exc}"
        raise GitError(msg, retryable=False) from exc
    if check and proc.returncode != 0:
        msg = f"git {args[0] if args else ''} exited {proc.returncode}: {proc.stderr.strip()[:300]}"
        raise GitError(msg, retryable=False)
    return proc.stdout


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
    """Return the repo-relative paths of all changed and untracked files."""
    # -uall lists each untracked FILE (git otherwise collapses an untracked dir).
    out = run_git(vault, "status", "--porcelain", "-uall", check=False)
    return [ln[3:].strip() for ln in out.splitlines() if ln.strip()]


__all__ = [
    "GitError",
    "dirty_rels",
    "has_conflict_markers",
    "has_upstream",
    "is_repo",
    "merge_in_progress",
    "readiness",
    "run_git",
    "show_stage",
    "sync_status",
    "unmerged_paths",
]
