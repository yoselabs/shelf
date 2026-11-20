"""git LFS for a program that owns a repo: configure it, ask which paths LFS owns, and move
objects before the refs that need them.

Three rules shape this module:

* **The filter lives in the repo's own config, marked required.** Attributes alone do
  nothing: with no ``filter.lfs.*`` configured, ``git add`` stores the raw bytes. With
  ``required``, a broken or missing git-lfs fails the add instead.
* **No hooks.** ``git lfs install`` would add pre-push / post-checkout hooks; nothing here
  relies on them, so a host must call :func:`lfs_push` before it pushes.
* **Objects move outside git's checkout.** :func:`lfs_fetch` downloads before a merge, so
  the merge's checkout finds every object locally; a download failing inside a checkout
  makes git restore the tree, which can itself fail and leave it dirty.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from child_env import NotFound, find

from git_porcelain.errors import GitError
from git_porcelain.history import _remote
from git_porcelain.porcelain import git_env, git_returncode, run_git, try_git

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from git_porcelain.api import CommandResult

_FILTER = {
    "filter.lfs.process": "git-lfs filter-process",
    "filter.lfs.clean": "git-lfs clean -- %f",
    "filter.lfs.smudge": "git-lfs smudge -- %f",
    "filter.lfs.required": "true",
}


def lfs_available(*, ambient: Mapping[str, str]) -> bool:
    """True when ``git lfs`` runs with ``ambient`` as its environment."""
    env = git_env(ambient)
    try:
        find("git", env)
        find("git-lfs", env)
    except NotFound:
        return False
    try:
        return git_returncode(Path.cwd(), "lfs", "version", ambient=ambient) == 0
    except GitError:
        return False


def lfs_setup(repo: Path, *, ambient: Mapping[str, str]) -> bool:
    """Configure LFS in ``repo``'s local config; True when LFS is ready to commit through.

    Idempotent: a value already set is not rewritten. Returns False, changing nothing, when
    git-lfs is not available. Touches no working-tree file and makes no network call:
    pointer files already on disk wait for :func:`lfs_fetch` and :func:`lfs_checkout`.
    """
    if not lfs_available(ambient=ambient):
        return False
    for key, value in _FILTER.items():
        current = try_git(repo, "config", "--local", "--get", key, ambient=ambient).strip()
        if current != value:
            run_git(repo, "config", "--local", key, value, ambient=ambient)
    return True


def lfs_checkout(repo: Path, *, ambient: Mapping[str, str]) -> None:
    """Replace pointer files in the working tree with bytes already in the local LFS store.

    Touches nothing else; a pointer whose object is not local stays a pointer.
    """
    if git_returncode(repo, "rev-parse", "--verify", "-q", "HEAD", ambient=ambient) == 0:
        run_git(repo, "lfs", "checkout", ambient=ambient)


def lfs_paths(repo: Path, paths: Iterable[str], *, ambient: Mapping[str, str]) -> set[str]:
    """The subset of ``paths`` (repo-relative) whose ``filter`` attribute is ``lfs``."""
    wanted = list(dict.fromkeys(paths))
    if not wanted:
        return set()
    out = run_git(repo, "check-attr", "-z", "filter", "--", *wanted, ambient=ambient)
    fields = out.split("\0")
    owned: set[str] = set()
    for i in range(0, len(fields) - 2, 3):
        path, _attr, value = fields[i : i + 3]
        if value == "lfs":
            owned.add(path)
    return owned


def lfs_push(
    repo: Path, remote: str, ref: str, *, ambient: Mapping[str, str], timeout: float = 600, config: Mapping[str, str] | None = None
) -> CommandResult:
    """Upload the LFS objects ``ref`` references to ``remote``. Call before ``git push``."""
    return _remote(repo, "lfs", "push", remote, ref, timeout=timeout, config=config, ambient=ambient)


def lfs_fetch(
    repo: Path, remote: str, ref: str, *, ambient: Mapping[str, str], timeout: float = 600, config: Mapping[str, str] | None = None
) -> CommandResult:
    """Download the LFS objects ``ref`` references from ``remote``. Call before a merge."""
    return _remote(repo, "lfs", "fetch", remote, ref, timeout=timeout, config=config, ambient=ambient)
