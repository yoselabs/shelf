#!/usr/bin/env python3
"""The files a per-file linter must look at: those changed against the base, matching its globs.

Prints repo-relative paths, NUL-separated (`xargs -0`, `mapfile -d ''`). A file counts when it differs from the
upstream merge-base (the base `tools/affected.py` uses): committed on the branch, staged, unstaged, or untracked
and not ignored. A deleted file never counts (only existing files are printed); a renamed one counts by its new path.

Everything (every tracked or untracked-not-ignored file matching the globs) is printed instead when:
- `--scope all` (what `just check-all`, which CI runs, passes), or
- a `--config` file changed (a linter's rules moved, so files that were clean may not be), or
- there is no base: not a git repo, no upstream, or git fails. Run too much rather than too little.

Globs are fnmatch patterns on the whole path, where `*` crosses `/`: `packages/*.py` is every .py under packages.
Stdlib only, so it runs as bare `python3`.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

_SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__"}


def _git(repo: Path, *args: str) -> list[str] | None:
    """Lines git prints, or None when git fails (not a repo, no upstream, ...)."""
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    return done.stdout.split("\0") if done.returncode == 0 else None


def base(repo: Path) -> str | None:
    """The upstream merge-base, the same base `tools/affected.py` diffs against; None when there is none."""
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
    tracked = _git(repo, "diff", "-z", "--name-only", start)
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=".", help="the repo (default: cwd)")
    parser.add_argument("--scope", choices=("changed", "all"), default="changed")
    parser.add_argument("--config", action="append", default=[], help="a file (or glob) whose change selects everything")
    parser.add_argument("--not", dest="skip", action="append", default=[], metavar="GLOB", help="never select a path matching this")
    parser.add_argument("patterns", nargs="+", metavar="GLOB")
    args = parser.parse_args()
    files = select(Path(args.repo).resolve(), args.patterns, args.config, skip=args.skip, scope=args.scope)
    sys.stdout.write("".join(f"{p}\0" for p in files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
