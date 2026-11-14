"""``Worktree.start_merge``, ``merging``, ``finish_merge`` and ``abort_merge`` over the git binary.

A merge of one commit into a checkout, stopped before its commit (``git merge --no-ff --no-commit``): clean changes staged,
conflicts as markers, ``MERGE_HEAD`` recording the second parent. The caller edits and stages, then finishes (one commit
that moves HEAD only) or aborts. No ref is written by any of them; a detached checkout keeps no branch to move.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from git_porcelain.api_results import MergeStarted, Sha, UpToDate
from git_porcelain.errors import UnmergedPaths, some
from git_porcelain.real_checkout import resolve_commit
from git_porcelain.real_done import unavailable
from git_porcelain.real_read import dirty, git_dir_of, head_of, unmerged
from git_porcelain.real_write import _identity_args

if TYPE_CHECKING:
    from git_porcelain.real import RealWorktree

__all__ = ["abort_merge", "finish_merge", "merging", "start_merge"]


def merging(wt: RealWorktree) -> bool:
    return wt.run("rev-parse", "-q", "--verify", "MERGE_HEAD", check=False).rc == 0


def _paused_rebase(wt: RealWorktree) -> bool:
    gd = git_dir_of(wt)
    return (gd / "rebase-merge").is_dir() or (gd / "rebase-apply").is_dir()


def start_merge(wt: RealWorktree, rev: str) -> MergeStarted | UpToDate:
    target = resolve_commit(wt, rev)
    if merging(wt) or _paused_rebase(wt):
        msg = "a merge or rebase is already under way here: finish or abort it first"
        raise ValueError(msg)
    if dirty(wt, None, ()).tracked:
        msg = "dirty: the tree has tracked changes"
        raise ValueError(msg)
    try:
        done = wt.run("merge", "--no-ff", "--no-commit", "--no-verify", "--no-edit", target, check=False)
        if merging(wt):
            return MergeStarted(Sha(target), unmerged(wt), output=done.output)
        if done.rc == 0:
            return UpToDate(done.output)
        raise unavailable(("merge",), done)
    finally:
        wt.repo.invalidate()


def finish_merge(wt: RealWorktree, message: str) -> Sha:
    if not merging(wt):
        msg = "no merge is under way here"
        raise ValueError(msg)
    paths = unmerged(wt)
    if paths:
        text = f"the index has unresolved merge entries: {', '.join(paths)}"
        raise UnmergedPaths(text, paths)
    try:
        done = wt.repo.run(wt.path, *_identity_args(wt.repo), "commit", "-q", "--no-verify", "--allow-empty", "-m", message, check=False)
        if done.rc:
            raise unavailable(("commit",), done)
    finally:
        wt.repo.invalidate()
    return some(head_of(wt))


def abort_merge(wt: RealWorktree) -> None:
    if not merging(wt):
        return
    try:
        done = wt.run("merge", "--abort", check=False)
        if done.rc:
            raise unavailable(("merge",), done)
    finally:
        wt.repo.invalidate()
