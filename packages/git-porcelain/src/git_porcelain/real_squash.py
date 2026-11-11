"""``Repo.squash`` over the git binary: one commit in Git objects only, never a checkout, an index or a ref.

``merge-tree --write-tree`` merges ``head`` onto ``onto`` (their merge base as the base) and writes the result's
trees; ``commit-tree`` makes the one commit whose parent is ``onto``. Neither runs a hook; signing is turned off
explicitly; author and committer are the repository's identity (``RealRepo(identity=...)``, else git's config).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from git_porcelain.api_results import Conflicted, Sha, Squashed, TreeId
from git_porcelain.errors import GitReadFailure
from git_porcelain.real_checkout import resolve_commit
from git_porcelain.real_done import unavailable

if TYPE_CHECKING:
    from git_porcelain.api_results import SquashResult
    from git_porcelain.real import RealRepo

__all__ = ["squash"]


def _identity(repo: RealRepo) -> list[str]:
    who = repo.who
    return [] if who is None else ["-c", f"user.name={who.name}", "-c", f"user.email={who.email}"]


def squash(repo: RealRepo, onto: str, head: str, message: str) -> SquashResult:
    wt = repo.worktree(repo.path)
    base, tip = resolve_commit(wt, onto), resolve_commit(wt, head)
    args = ("merge-tree", "--write-tree", "-z", "--name-only", "--no-messages", base, tip)
    merged = repo.run(repo.path, *args, check=False)
    if merged.rc not in (0, 1):
        raise unavailable(args, merged)
    parts = [part for part in merged.out.split("\0") if part]
    if not parts or (merged.rc == 1) != (len(parts) > 1):
        msg = f"merge-tree returned a malformed result: {merged.output}"
        raise GitReadFailure(msg)
    tree, *paths = parts
    if paths:
        return Conflicted(tuple(paths))
    made = repo.run(repo.path, *_identity(repo), "commit-tree", "--no-gpg-sign", "-p", base, "-F", "-", tree, stdin=message)
    return Squashed(Sha(made.out.strip()), TreeId(tree))
