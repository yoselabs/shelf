"""The files a per-file linter must look at: those changed against the base, matching its globs.

A file counts when it differs from the upstream merge-base (the base the test selector diffs against): committed on the branch, staged,
unstaged, or untracked and not ignored. A deleted file never counts (only existing files are returned); a renamed one counts by its
new path. `changed()` itself lists both paths of a move, so a step whose inputs name only the old folder still starts.

Everything (every tracked or untracked-not-ignored file matching the globs) is returned instead when:
- `scope="all"` (what `just check-all` passes), or
- a `configs` file changed (a linter's rules moved, so files that were clean may not be), or
- there is no base: not a git repo, no upstream, or git fails. Run too much rather than too little.

Globs are fnmatch patterns on the whole path, where `*` crosses `/`: `packages/*.py` is every .py under packages.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import TYPE_CHECKING

from stream_proc import capture

if TYPE_CHECKING:
    from collections.abc import Sequence

_SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__"}
SKIPPED_PREFIX = "skipped "
GIT_TIMEOUT = 600.0  # seconds one git call may take


def _git(repo: Path, *args: str) -> list[str] | None:
    """Lines git prints, or None when git fails (not a repo, no upstream, ...)."""
    done = capture(["git", *args], cwd=repo, timeout=GIT_TIMEOUT)
    return done.text.split("\0") if done.exit == 0 else None


def base(repo: Path) -> str | None:
    """The upstream merge-base, the same base the test selector diffs against; None when there is none."""
    found = _git(repo, "merge-base", "HEAD", "@{upstream}")
    return found[0].strip() if found and found[0].strip() else None


def everything(repo: Path) -> list[str]:
    """Every tracked and untracked-not-ignored file; outside a git repo, every file below `repo`."""
    listed = _git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if listed is not None:
        return sorted(p for p in set(listed) if p)
    walked: list[str] = []
    for root, dirs, names in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        walked += [(Path(root) / n).relative_to(repo).as_posix() for n in names]
    return sorted(walked)


def changed(repo: Path) -> list[str] | None:
    """Changed paths since the base, or None when there is no base (the caller then takes everything)."""
    start = base(repo)
    if start is None:
        return None
    # --no-renames: a move changes BOTH paths, and a step reading the old one must see it
    tracked = _git(repo, "diff", "-z", "--name-only", "--no-renames", start)
    untracked = _git(repo, "ls-files", "-z", "--others", "--exclude-standard")
    if tracked is None or untracked is None:
        return None
    return sorted({p for p in (*tracked, *untracked) if p})


def select(repo: Path, patterns: list[str], configs: Sequence[str] = (), *, skip: Sequence[str] = (), scope: str = "changed") -> list[str]:
    """The existing files matching `patterns` that the linter must check (see the module docstring)."""
    moved = changed(repo) if scope != "all" else None
    config_moved = moved is not None and any(fnmatch.filter(moved, c) for c in configs)
    pool = everything(repo) if moved is None or config_moved else moved

    def wanted(path: str) -> bool:
        return (
            (repo / path).is_file()
            and any(fnmatch.fnmatchcase(path, g) for g in patterns)
            and not any(fnmatch.fnmatchcase(path, g) for g in skip)
        )

    return [p for p in pool if wanted(p)]
