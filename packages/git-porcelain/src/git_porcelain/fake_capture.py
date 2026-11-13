"""``Worktree.capture``, ``Repo.commit_tree`` and ``Repo.update_ref`` in memory, with the contract the git binary showed."""

from __future__ import annotations

from typing import TYPE_CHECKING

from git_porcelain.api_results import RefMoved, RefUpdated, Sha, TreeId
from git_porcelain.errors import GitUnavailable, MissingRevision, UnmergedPaths
from git_porcelain.fake_ops import stage
from git_porcelain.fake_read import resolve_commit
from git_porcelain.revision_validation import validate_revisions

if TYPE_CHECKING:
    from git_porcelain.api_results import RefUpdate
    from git_porcelain.fake_store import CheckoutState, RepoState

__all__ = ["capture", "commit_tree", "update_ref"]


def capture(repo: RepoState, wt: CheckoutState) -> TreeId:
    if wt.unmerged:
        paths = tuple(sorted(wt.unmerged))
        msg = f"the index has unresolved merge entries: {', '.join(paths)}"
        raise UnmergedPaths(msg, paths)
    saved = dict(wt.index)
    try:
        stage(repo, wt, None)
        return TreeId(repo.store.put_tree(wt.index))
    finally:
        wt.index = saved


def commit_tree(repo: RepoState, wt: CheckoutState, tree: str, parents: tuple[str, ...], message: str, *, when: int | None) -> Sha:
    validate_revisions(tree, *parents)
    files = repo.store.trees.get(tree)
    if files is None:
        msg = f"git: bad revision '{tree}'"
        raise MissingRevision(msg)
    shas = tuple(resolve_commit(repo, wt, parent) for parent in parents)
    if when is not None:  # fixed identity and date make git's commit id a function of its content
        for known in repo.store.commits.values():
            if (known.tree, known.parents, known.message) == (tree, shas, message):
                return Sha(known.sha)
    return Sha(repo.store.put_commit(files, shas, message, repo.tick()).sha)


def update_ref(repo: RepoState, wt: CheckoutState, ref: str, new: str, expected: str | None) -> RefUpdate:
    validate_revisions(new, *([expected] if expected is not None else []))
    if not ref.startswith("refs/"):
        msg = f"update_ref needs a full ref name, got {ref!r}"
        raise ValueError(msg)
    if ref in repo.symbolic_refs:
        msg = f"git: {ref} is a symbolic ref"
        raise GitUnavailable(msg)
    target = resolve_commit(repo, wt, new)
    actual = repo.refs.get(ref)
    if actual != (None if expected is None else resolve_commit(repo, wt, expected)):
        return RefMoved(None if actual is None else Sha(actual))
    repo.refs[ref] = target
    return RefUpdated(Sha(target))
