#!/usr/bin/env python3
"""No tracked file or package is named like a standard library module where a script run puts it on sys.path first.

Python puts the running script's folder first on `sys.path`, ahead of the standard library. A `queue.py` beside the scripts then
replaces `queue` for every script run from there (a consumer repo: 729 jobs failed with `module 'queue' has no attribute
'SimpleQueue'`; a `profile.py` shadows the profiler `cProfile` imports). This checks, from `sys.stdlib_module_names`, every `*.py` file
and every package directory (one holding `__init__.py`) whose name is a standard library module.

A name is checked in a folder that can be the first on `sys.path`: the repo root, a folder named `scripts`, `tools`, `bin`, `src`,
`tests` or `test`, or any folder with a `*.py` that has a `__main__` guard or a PEP 723 `# /// script` header (a script a person
runs). A folder inside a package (it, or a folder above it below the repo root, has `__init__.py`) is not checked: its modules are
imported by their package name and relative imports apply, so `src/<pkg>/queue.py` is safe. `src/` itself is checked, being on the
path of an editable install. `__main__.py` is never a shadow. A namespace folder (no `__init__.py`) loses to the standard library,
so it is not one.

`tools/stdlib_shadow_allow.toml` lists the paths allowed to stay, each with its one-line reason. An entry with no reason, or for a path
that no longer shadows, fails too, so the list never outlives the need. Stdlib only, so it runs as bare `python3 -I`.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

ALLOW_FILE = Path(__file__).with_name("stdlib_shadow_allow.toml")
ROOT = PurePosixPath()  # the repo root, spelled as a folder
GIT_TIMEOUT = 60.0
SCRIPT_DIRS = frozenset({"scripts", "tools", "bin", "src", "tests", "test"})  # run from, an editable install's path, put first by pytest
SCRIPT_MARK = re.compile(r"""^if\s+__name__\s*==\s*["']__main__["']|^#\s*///\s*script\s*$""", re.MULTILINE)
NOT_SHADOWS = frozenset({"__main__"})  # the stdlib set lists it; a `__main__.py` is how a folder is run, never an import target


def tracked_python(repo: Path) -> list[str]:
    """Repo-relative `*.py` paths git tracks or would track (new, not ignored); empty when git cannot say."""
    try:
        done = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*.py"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return []
    return sorted({p for p in done.stdout.split("\0") if p and (repo / p).is_file()}) if done.returncode == 0 else []


def shadows(repo: Path, paths: Sequence[str]) -> dict[str, str]:
    """{path: stdlib module it shadows} for each file or package dir that sits on a script's sys.path."""
    files = {PurePosixPath(p) for p in paths}
    packages = {p.parent for p in files if p.name == "__init__.py"}

    def marked(path: PurePosixPath) -> bool:
        text = (repo / path).read_text(encoding="utf-8", errors="replace")  # lossy-ok: detect: only a marker is searched for
        return SCRIPT_MARK.search(text) is not None

    scripty = {p.parent for p in files if marked(p)}

    def inside_package(folder: PurePosixPath) -> bool:
        return any(up in packages for up in (folder, *folder.parents) if up != ROOT)

    def on_path(folder: PurePosixPath) -> bool:
        return not inside_package(folder) and (folder == ROOT or folder.name in SCRIPT_DIRS or folder in scripty)

    out: dict[str, str] = {}
    for p in sorted(files):
        if p.name != "__init__.py" and p.stem in sys.stdlib_module_names and p.stem not in NOT_SHADOWS and on_path(p.parent):
            out[str(p)] = p.stem
    for pkg in sorted(packages):
        if pkg.name in sys.stdlib_module_names and on_path(pkg.parent):
            out[str(pkg)] = pkg.name
    return out


def problems(found: dict[str, str], allow: dict[str, object]) -> list[str]:
    """The lines to print: shadows not allowed, allowance entries with no reason, and entries that no longer shadow."""
    out = [
        f"{path}: shadows the standard library module `{name}` for any script run from its folder "
        f"(rename it, or allow it in {ALLOW_FILE.name} with a reason)"
        for path, name in found.items()
        if path not in allow
    ]
    for path, reason in sorted(allow.items()):
        if not isinstance(reason, str) or not reason.strip():
            out.append(f"{ALLOW_FILE.name}: {path} has no reason; every entry needs a one-line reason")
        elif path not in found:
            out.append(f"{ALLOW_FILE.name}: {path} no longer shadows anything; delete its entry ({reason})")
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--allow", type=Path, default=ALLOW_FILE)
    args = parser.parse_args(argv)
    allow = tomllib.loads(args.allow.read_text(encoding="utf-8")).get("allow", {}) if args.allow.is_file() else {}
    bad = problems(shadows(args.repo, tracked_python(args.repo)), allow)
    for line in bad:
        sys.stderr.write(f"stdlib-shadow: {line}\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
