"""``Worktree.start_merge``, ``merging``, ``finish_merge`` and ``abort_merge`` in memory, with the contract the git binary showed."""

from __future__ import annotations

from typing import TYPE_CHECKING

from git_porcelain.api_results import MergeStarted, Sha, UpToDate
from git_porcelain.errors import GitUnavailable, UnmergedPaths, some
from git_porcelain.fake_flow import stop
from git_porcelain.fake_merge import merge_trees
from git_porcelain.fake_ops import hard_to, make_commit, require_index, tracked_dirty
from git_porcelain.fake_read import relate, resolve_commit
from git_porcelain.fake_store import ancestors

if TYPE_CHECKING:
    from git_porcelain.fake_store import CheckoutState, RepoState

__all__ = ["abort_merge", "finish_merge", "start_merge"]


def start_merge(repo: RepoState, wt: CheckoutState, rev: str) -> MergeStarted | UpToDate:
    target = resolve_commit(repo, wt, rev)
    if wt.merge_head is not None or wt.rebase is not None:
        msg = "a merge or rebase is already under way here: finish or abort it first"
        raise ValueError(msg)
    if tracked_dirty(wt, repo.head_files(wt)):
        msg = "dirty: the tree has tracked changes"
        raise ValueError(msg)
    require_index(wt)
    head = some(repo.head_sha(wt))
    if target in ancestors(repo.store, head):
        return UpToDate()
    fork = relate(repo, wt, head, target).merge_base
    if fork is None:
        msg = "git: refusing to merge unrelated histories"
        raise GitUnavailable(msg)
    merged, conflicts = merge_trees(repo, repo.store.commits[fork].files, dict(repo.head_files(wt)), repo.store.commits[target].files)
    stop(repo, wt, merged, conflicts)
    wt.merge_head = target
    return MergeStarted(Sha(target), tuple(sorted(conflicts)))


def finish_merge(repo: RepoState, wt: CheckoutState, message: str) -> Sha:
    if wt.merge_head is None:
        msg = "no merge is under way here"
        raise ValueError(msg)
    require_index(wt)
    if wt.unmerged:
        paths = tuple(sorted(wt.unmerged))
        msg = f"the index has unresolved merge entries: {', '.join(paths)}"
        raise UnmergedPaths(msg, paths)
    made = make_commit(repo, wt, message, (some(repo.head_sha(wt)), wt.merge_head))
    wt.merge_head = None
    return Sha(made)


def abort_merge(repo: RepoState, wt: CheckoutState) -> None:
    if wt.merge_head is None:
        return
    head = some(repo.head_sha(wt))
    hard_to(repo, wt, repo.store.commits[head].files, repo.head_files(wt))
    wt.unmerged.clear()
    wt.merge_head = None
