"""Exact-tree capture, ``commit_tree`` and compare-and-swap ``update_ref`` over the git binary.

Capture builds the tree in a private copy of the checkout's index (``GIT_INDEX_FILE``), so the real index, HEAD and
every ref stay as they were: the copy starts from the paths already indexed (an indexed path stays in even if an
ignore rule now matches it), ``add -A`` makes the working files win over what was staged and leaves ignored untracked
files out, and ``write-tree`` names the result. ``commit_tree`` and ``update_ref`` write Git objects and one ref only.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from git_porcelain.api_results import RefMoved, RefUpdated, Sha, TreeId
from git_porcelain.errors import EmbeddedRepositories, GitReadFailure, MissingRevision, RefRace, UnmergedPaths
from git_porcelain.real_checkout import resolve_commit
from git_porcelain.real_read import head_of
from git_porcelain.revision_validation import validate_revisions

if TYPE_CHECKING:
    from git_porcelain.api_results import RefUpdate
    from git_porcelain.real import RealRepo, RealWorktree

__all__ = ["capture", "commit_tree", "update_ref"]

_GITLINK = "160000"


def _entries(wt: RealWorktree, *args: str, env: dict[str, str] | None = None) -> list[str]:
    return [part for part in wt.run(*args, "-z", env=env).out.split("\0") if part]


def _gitlinks(wt: RealWorktree, env: dict[str, str] | None) -> set[str]:
    rows = (row.partition("\t") for row in _entries(wt, "ls-files", "--stage", env=env))
    return {path for meta, _, path in rows if meta.startswith(_GITLINK)}


def capture(wt: RealWorktree) -> TreeId:
    """The tree of the checkout's final working state; see ``Worktree.capture``."""
    unmerged = sorted({row.partition("\t")[2] for row in _entries(wt, "ls-files", "--unmerged")})
    if unmerged:
        msg = f"the index has unresolved merge entries: {', '.join(unmerged)}"
        raise UnmergedPaths(msg, tuple(unmerged))
    index = Path(wt.run("rev-parse", "--git-path", "index").out.strip())
    source = index if index.is_absolute() else wt.path / index
    with tempfile.TemporaryDirectory(prefix="git-porcelain-capture-") as folder:
        copy = Path(folder) / "index"
        env = {"GIT_INDEX_FILE": str(copy)}
        if source.exists():
            shutil.copyfile(source, copy)
        elif head_of(wt) is not None:
            wt.run("read-tree", "HEAD", env=env)
        before = _gitlinks(wt, env)
        wt.run("add", "-A", env=env)
        nested = sorted(_gitlinks(wt, env) - before)
        if nested:
            msg = f"a repository nested in the checkout cannot be captured: {', '.join(nested)}"
            raise EmbeddedRepositories(msg, tuple(nested))
        return TreeId(wt.run("write-tree", env=env).out.strip())


def commit_tree(repo: RealRepo, tree: str, parents: tuple[str, ...], message: str, *, when: int | None) -> Sha:
    validate_revisions(tree, *parents)
    wt = repo.worktree(repo.path)
    if wt.run("rev-parse", "--verify", "-q", "--end-of-options", f"{tree}^{{tree}}", check=False).rc != 0:
        msg = f"git: bad tree '{tree}'"
        raise MissingRevision(msg)
    args = ["commit-tree", "--no-gpg-sign"]
    for parent in parents:
        args += ["-p", resolve_commit(wt, parent)]
    who = repo.who
    ident = [] if who is None else ["-c", f"user.name={who.name}", "-c", f"user.email={who.email}"]
    stamp = {} if when is None else {"GIT_AUTHOR_DATE": f"{when} +0000", "GIT_COMMITTER_DATE": f"{when} +0000"}
    made = repo.run(repo.path, *ident, *args, "-F", "-", f"{tree}^{{tree}}", stdin=message, env=stamp)
    return Sha(made.out.strip())


def _current(repo: RealRepo, ref: str) -> Sha | None:
    done = repo.run(repo.path, "for-each-ref", "--format=%(objectname)", "--", ref)
    found = done.out.split()
    if len(found) > 1:
        msg = f"for-each-ref returned several refs for {ref}"
        raise GitReadFailure(msg, output=done.output)
    return Sha(found[0]) if found else None


def update_ref(repo: RealRepo, ref: str, new: str, expected: str | None) -> RefUpdate:
    validate_revisions(new, *([expected] if expected is not None else []))
    if not ref.startswith("refs/"):
        msg = f"update_ref needs a full ref name, got {ref!r}"
        raise ValueError(msg)
    target = resolve_commit(repo.worktree(repo.path), new)
    old = "0" * len(target) if expected is None else expected
    try:
        repo.run(repo.path, "update-ref", "--no-deref", ref, target, old)
    except RefRace:
        return RefMoved(_current(repo, ref))
    finally:
        repo.invalidate()
    return RefUpdated(Sha(target))
