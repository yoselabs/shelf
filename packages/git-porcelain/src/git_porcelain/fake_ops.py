"""FakeGit's writes: stage, commit, switch, reset, clean. Each takes the repository and the checkout."""

from __future__ import annotations

from typing import TYPE_CHECKING

from git_porcelain.errors import GitError
from git_porcelain.fake_diff import status_entries
from git_porcelain.fake_ignore import Ignore
from git_porcelain.fake_store import blob_sha

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from git_porcelain.fake_store import Repo, WorkTree

__all__ = [
    "branch_ref",
    "check_branch_free",
    "clean",
    "commit",
    "hard_to",
    "ignore_of",
    "is_clean",
    "stage",
    "switch_tree",
    "tracked_dirty",
]


def ignore_of(wt: WorkTree, extra: Sequence[str] = ()) -> Ignore:
    """The checkout's root ``.gitignore`` after ``extra`` rules (which it overrides)."""
    return Ignore([*extra, *wt.files.get(".gitignore", b"").decode("utf-8", "replace").splitlines()])


def branch_ref(name: str) -> str:
    return f"refs/heads/{name}"


def check_branch_free(repo: Repo, wt: WorkTree, ref: str) -> None:
    """A branch checked out in another worktree cannot be taken here."""
    for other in repo.worktrees.values():
        if other is not wt and other.head_ref == ref:
            msg = f"git: '{ref.removeprefix('refs/heads/')}' is already used by worktree at '{other.path}'"
            raise GitError(msg)


def tracked_dirty(wt: WorkTree, head: Mapping[str, str]) -> bool:
    """True when the index or a tracked file differs from the HEAD tree."""
    if dict(wt.index) != dict(head):
        return True
    return any(p not in wt.files or blob_sha(wt.files[p]) != sha for p, sha in wt.index.items())


def _modified(wt: WorkTree, old: Mapping[str, str], path: str) -> bool:
    data = wt.files.get(path)
    return wt.index.get(path) != old.get(path) or (path in wt.index and (data is None or blob_sha(data) != wt.index[path]))


def switch_tree(repo: Repo, wt: WorkTree, new: Mapping[str, str], old: Mapping[str, str]) -> None:
    """Move index and files from the ``old`` tree to ``new`` the way ``checkout`` does: untouched paths keep
    local edits, a path that would lose an edit (or an untracked file) raises."""
    changed = [p for p in sorted(set(old) | set(new)) if old.get(p) != new.get(p)]
    for path in changed:
        if _modified(wt, old, path) or (path not in wt.index and path in wt.files and path in new):
            msg = f"git: your local changes to '{path}' would be overwritten by checkout"
            raise GitError(msg)
    for path in changed:
        if path in new:
            wt.index[path] = new[path]
            wt.files[path] = repo.store.blobs[new[path]]
        else:
            wt.index.pop(path, None)
            wt.files.pop(path, None)


def hard_to(repo: Repo, wt: WorkTree, new: Mapping[str, str], old: Mapping[str, str]) -> None:
    """``reset --hard``: every tracked path becomes the ``new`` tree's, edits and all."""
    for path in set(wt.index) | set(old):
        if path not in new:
            wt.index.pop(path, None)
            wt.files.pop(path, None)
    for path, sha in new.items():
        wt.index[path] = sha
        wt.files[path] = repo.store.blobs[sha]
    wt.unmerged.clear()


def _matching(wt: WorkTree, spec: str) -> list[str]:
    names = set(wt.files) | set(wt.index)
    return [p for p in sorted(names) if p == spec or p.startswith(spec.rstrip("/") + "/")]


def _sync(repo: Repo, wt: WorkTree, path: str) -> None:
    if path in wt.files:
        wt.index[path] = repo.store.put_blob(wt.files[path])
    else:
        wt.index.pop(path, None)
    wt.unmerged.discard(path)


def stage(repo: Repo, wt: WorkTree, paths: Sequence[str] | None) -> None:
    """``add -A`` (all paths) or ``add -A`` on literal paths; ignored untracked files stay out."""
    ignore = ignore_of(wt)
    if paths is None:
        for path in sorted(set(wt.files) | set(wt.index)):
            if path in wt.index or not ignore.ignores(path):
                _sync(repo, wt, path)
        return
    for spec in paths:
        matched = _matching(wt, spec)
        if not matched:
            msg = f"git: pathspec '{spec}' did not match any files"
            raise GitError(msg)
        blocked = [p for p in matched if p not in wt.index and ignore.ignores(p)]
        if blocked and len(blocked) == len(matched):
            msg = f"git: the following paths are ignored by one of your .gitignore files: {' '.join(blocked)}"
            raise GitError(msg)
        for path in matched:
            if path not in blocked:
                _sync(repo, wt, path)


def commit(repo: Repo, wt: WorkTree, message: str, *, allow_empty: bool) -> str:
    if wt.unmerged:
        msg = "git: committing is not possible because you have unmerged files"
        raise GitError(msg)
    head = repo.head_sha(wt)
    if dict(wt.index) == dict(repo.head_files(wt)) and not allow_empty:
        msg = "git commit exited 1: nothing to commit"
        raise GitError(msg)
    made = repo.store.put_commit(wt.index, (head,) if head else (), message, repo.tick())
    repo.move_head(wt, made.sha)
    return made.sha


def clean(wt: WorkTree, keep: Sequence[str]) -> None:
    """Remove untracked files that no ignore rule (the ``.gitignore`` or a ``keep`` pattern) protects."""
    ignore = ignore_of(wt, keep)
    for path in [p for p in wt.files if p not in wt.index and not ignore.ignores(p)]:
        del wt.files[path]


def is_clean(repo: Repo, wt: WorkTree) -> bool:
    """True when ``status`` would list nothing (untracked files count)."""
    return not status_entries(repo.head_files(wt), wt, ignore_of(wt))
