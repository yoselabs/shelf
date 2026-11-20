"""Pinned worktree pool operations and raw status state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from git_porcelain.errors import GitUnavailable, NotARepo, NotAWorktree, WorktreeRemoveRefused
from git_porcelain.real_done import unavailable
from git_porcelain.revision_validation import validate_revisions

if TYPE_CHECKING:
    from pathlib import Path

    from git_porcelain.real import RealRepo, RealWorktree

__all__ = ["add_worktree", "discard_worktree", "drop_worktree", "prune_worktrees", "worktree_state"]


def add_worktree(repo: RealRepo, path: Path, rev: str) -> RealWorktree:
    validate_revisions(rev)
    try:
        repo.run(repo.path, "worktree", "add", "-q", "--detach", "--", str(path), rev)
    finally:
        repo.invalidate()
    return repo.worktree(path)


def drop_worktree(repo: RealRepo, path: Path) -> None:
    _remove(repo, path, ())


def discard_worktree(repo: RealRepo, path: Path) -> None:
    _remove(repo, path, ("--force",))


def _remove(repo: RealRepo, path: Path, extra: tuple[str, ...]) -> None:
    args = ("worktree", "remove", *extra, str(path))
    try:
        done = repo.try_run(repo.path, *args)
        if done.rc:
            error = unavailable(args, done)
            if type(error) is not GitUnavailable:
                raise error
            lines = [line.strip() for line in done.err.splitlines() if line.strip()]
            last = lines[-1] if lines else "git worktree remove failed"
            reason = next((line for line in lines if line.startswith(("fatal:", "error:"))), last)
            refused = NotAWorktree if reason.endswith("is not a working tree") else WorktreeRemoveRefused
            raise refused(reason, code=done.rc, hint_line=last)
    finally:
        repo.invalidate()


def prune_worktrees(repo: RealRepo) -> None:
    try:
        repo.run(repo.path, "worktree", "prune")
    finally:
        repo.invalidate()


def worktree_state(repo: RealRepo, path: Path) -> bytes | None:
    args = ("--no-optional-locks", "status", "--porcelain=v2", "--branch", "-z", "--untracked-files=all")
    done = repo.try_run(path, *args)
    if done.rc == 0:
        return done.raw
    error = unavailable(args, done)
    if isinstance(error, NotARepo) or done.err.strip() == "fatal: this operation must be run in a work tree":
        return None
    raise error
