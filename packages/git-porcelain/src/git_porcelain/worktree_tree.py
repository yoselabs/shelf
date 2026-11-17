"""A folder on disk read the way a commit's tree is: ``Tree`` for the files of a checkout, uncommitted edits included."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from git_porcelain.api import Sha, Tree
from git_porcelain.fake_store import blob_sha as _blob_sha
from git_porcelain.fake_store import tree_sha

__all__ = ["blob_sha", "worktree_tree"]

_REGULAR, _EXECUTABLE = "100644", "100755"


def blob_sha(data: bytes) -> Sha:
    """The id Git gives a file holding ``data`` (``sha1("blob <n>\\0" + data)``), so a file on disk compares with a tree's."""
    return Sha(_blob_sha(data))


def worktree_tree(root: Path, folder: str = "") -> Tree | None:
    """The regular files below ``root/folder`` as a ``Tree``: ``files`` is path (relative to the folder) to
    ``(mode, blob sha)``, ``read`` and ``read_many`` give exact bytes (None when absent or not a regular file), and ``sha``
    is the id Git gives that tree for these files. None when the folder is absent or a file.

    Everything on disk counts, ignored files too; a ``.git`` entry, symlinks and empty folders do not. The listing is a
    snapshot taken here; file contents are read when asked, so an edit after this call is seen by ``read``."""
    base = root / folder if folder.strip("/") else root
    if not base.is_dir():
        return None
    blobs: dict[str, str] = {}
    modes: dict[str, str] = {}
    for found in sorted(base.rglob("*")):
        rel = found.relative_to(base)
        if ".git" in rel.parts or found.is_symlink() or not found.is_file():
            continue
        path = rel.as_posix()
        blobs[path] = _blob_sha(found.read_bytes())
        modes[path] = _EXECUTABLE if found.stat().st_mode & 0o111 else _REGULAR

    def read(path: str) -> bytes | None:
        parts = PurePosixPath(path).parts
        if not parts or path.startswith("/") or ".." in parts or ".git" in parts:
            return None
        target = base / path
        return target.read_bytes() if target.is_file() and not target.is_symlink() else None

    return Tree(
        Sha(tree_sha(blobs, modes)),
        lambda: {p: (modes[p], Sha(s)) for p, s in blobs.items()},
        read,
    )
