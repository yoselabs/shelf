"""Gate lint paths: `[tool.blueprint.gate] lint-paths` narrows what ruff reads; a Python file outside it is never linted.

The rendered lint recipe runs ruff inside the Python stack's folder (ADR 0034), so an entry is relative to that folder: `src` in
`backend/` is `backend/src`, and `../.a2kay/jobs` is `.a2kay/jobs`. The row reads them the same way, as repo paths.
"""

from __future__ import annotations

import posixpath

from blueprint import gate_py, ruff_rules
from blueprint.model import Context, Finding, failing, is_skipped, not_applicable, not_checked, passing

_SHOWN = 8


def lint_paths_cover(ctx: Context) -> Finding:
    """Every `git ls-files *.py` sits under a `lint-paths` entry (a folder holds what is below it; a file is itself)."""
    folder = ctx.py_folder()
    entries = gate_py.lint_paths(ctx.repo)
    if not entries:
        return not_applicable(f"no lint-paths: ruff reads {'the repo root' if folder == '.' else folder}")
    # A repo path per entry; an entry above the folder (`..`) is the repo root, an entry above that reaches outside the repo.
    paths = [gate_py.norm(posixpath.join(folder, e)) for e in entries]
    listed = ctx.git("ls-files", "-z", "--", "*.py")
    if listed is None:
        return not_checked("git cannot list the tracked files")
    files = [f for f in listed.split("\0") if f]
    skipped = ruff_rules.excluded(ctx)
    outside = [f for f in files if not is_skipped(f, skipped) and not gate_py.under(f, paths)]
    if not outside:
        return passing(f"{len(files)} tracked .py files, all under lint-paths ({', '.join(entries)})")
    folders = sorted({f.rsplit("/", 1)[0] if "/" in f else f for f in outside})
    shown = ", ".join(folders[:_SHOWN]) + (f" and {len(folders) - _SHOWN} more" if len(folders) > _SHOWN else "")
    return failing(
        f"{len(outside)} tracked .py files sit outside lint-paths and are never linted: {shown}",
        f"add {', '.join(repr(_entry(folder, f)) for f in folders[:_SHOWN])} to lint-paths in [tool.blueprint.gate] of "
        f"{ctx.py('pyproject.toml')}, or drop lint-paths to lint {'the repo root' if folder == '.' else folder}",
    )


def _entry(stack_folder: str, repo_path: str) -> str:
    """`repo_path` as a lint-paths entry: relative to the stack folder (`tests` for `backend/tests`, `../.a2kay/jobs` for `.a2kay/jobs`)."""
    return posixpath.relpath(repo_path, stack_folder)
