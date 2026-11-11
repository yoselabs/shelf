"""``Repo.squash`` in memory: ``fake_merge.merge_trees`` of ``head`` onto ``onto`` over their merge base, then one
commit object whose parent is ``onto``. No ref, checkout or index changes, as with ``merge-tree`` and ``commit-tree``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from git_porcelain.api_results import Conflicted, Sha, Squashed, TreeId
from git_porcelain.errors import GitUnavailable
from git_porcelain.fake_merge import merge_trees
from git_porcelain.fake_read import resolve_commit
from git_porcelain.fake_store import ancestors

if TYPE_CHECKING:
    from git_porcelain.api_results import SquashResult
    from git_porcelain.fake_store import CheckoutState, RepoState

__all__ = ["squash"]


def squash(repo: RepoState, wt: CheckoutState, onto: str, head: str, message: str) -> SquashResult:
    base, tip = resolve_commit(repo, wt, onto), resolve_commit(repo, wt, head)
    commits = repo.store.commits
    shared = ancestors(repo.store, base) & ancestors(repo.store, tip)
    if not shared:
        msg = "fatal: refusing to merge unrelated histories"
        raise GitUnavailable(msg)
    common = max(shared, key=lambda sha: commits[sha].order)
    merged, conflicts = merge_trees(repo, commits[common].files, commits[base].files, commits[tip].files)
    if conflicts:
        return Conflicted(tuple(sorted(conflicts)))
    made = repo.store.put_commit(merged, (base,), message, repo.tick())
    return Squashed(Sha(made.sha), TreeId(made.tree))
