"""Gate lint paths: `[tool.blueprint.gate] lint-paths` narrows what ruff reads; a Python file outside it is never linted."""

from __future__ import annotations

from blueprint import gate_py, ruff_rules
from blueprint.model import Context, Finding, failing, is_skipped, not_applicable, not_checked, passing

_SHOWN = 8


def lint_paths_cover(ctx: Context) -> Finding:
    """Every `git ls-files *.py` sits under a `lint-paths` entry (a folder holds what is below it; a file is itself)."""
    paths = gate_py._paths(ctx.repo, "lint-paths")  # noqa: SLF001 -- the one reader of the setting: judging it must not re-parse it
    if not paths:
        return not_applicable("no lint-paths: ruff reads the repo root")
    listed = ctx.git("ls-files", "-z", "--", "*.py")
    if listed is None:
        return not_checked("git cannot list the tracked files")
    roots = [p.strip("/").removeprefix("./") for p in paths]
    files = [f for f in listed.split("\0") if f]
    skipped = ruff_rules.excluded(ctx)
    outside = [f for f in files if not is_skipped(f, skipped) and not any(r in {"", "."} or f == r or f.startswith(f"{r}/") for r in roots)]
    if not outside:
        return passing(f"{len(files)} tracked .py files, all under lint-paths ({', '.join(paths)})")
    folders = sorted({f.rsplit("/", 1)[0] if "/" in f else f for f in outside})
    shown = ", ".join(folders[:_SHOWN]) + (f" and {len(folders) - _SHOWN} more" if len(folders) > _SHOWN else "")
    return failing(
        f"{len(outside)} tracked .py files sit outside lint-paths and are never linted: {shown}",
        f"add {', '.join(repr(f) for f in folders[:_SHOWN])} to lint-paths in [tool.blueprint.gate] of pyproject.toml, "
        "or drop lint-paths to lint the repo root",
    )
