"""`layout.stacks-in-own-folders`: with two code bases the root holds repo-level files only (ADR 0034).

One code base stays at the root. Two code bases each live in a folder named `backend/` or `frontend/`: a Python, .NET, Go or Rust code
base is the backend, a node one the frontend. A node folder that only runs build tools (`node-tooling`) is a tool, not a code base.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from blueprint.concerns.stacks.profile_data import load_profiles
from blueprint.model import SKIP_DIRS, Context, Finding, FixedBy, check, failing, not_applicable, passing

if TYPE_CHECKING:
    from blueprint.model import Profile

_ID = "layout.stacks-in-own-folders"
_STATEMENT = "with two code bases the root holds repo-level files only: each lives in backend/ or frontend/ (ADR 0034)"
_NODE = frozenset({"node"})
_TOOLS = frozenset({"node-tooling"})
# Root folders that are never a code base's own: they belong to the repo (docs, deploy, per-repo tooling folders).
_REPO_LEVEL = frozenset({"docs", "deploy", "packaging", "contract", "scripts", "tools", "backend", "frontend", "packages"})
_PYTHON_FILES = ("pyproject.toml", "uv.lock", ".python-version", "pyrefly.toml", "ruff.toml")
_NODE_FILES = ("package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "tsconfig.json", "biome.json", "knip.json")
_NODE_SUFFIXES = (".js", ".mjs", ".cjs", ".ts", ".tsx", ".css", ".html")
_CODE_SUFFIX = {"backend": (".py", ".cs", ".go", ".rs"), "frontend": (".js", ".mjs", ".cjs", ".ts", ".tsx", ".html")}


def _nested(folder: str) -> bool:
    """A folder two levels down or hidden (`labs/juice-shop`, `.opencode`): a lab, a vendored app or a tool's own, no code base."""
    parts = Path(folder).parts if folder != "." else ()
    return len(parts) > 1 or any(p.startswith(".") for p in parts)


def code_bases(profile: Profile) -> list[tuple[str, str]]:
    """`(stack, folder)` per code base: a language stack, or one with no profile yet, at the root or one folder down; no node tool."""
    profiles = load_profiles()
    roots = dict(profile.stack_roots)
    return [
        (s, roots.get(s, "."))
        for s in profile.stacks
        if s not in _TOOLS
        and not _nested(roots.get(s, "."))
        and (s not in profiles or profiles[s].family == "language")
        and s not in {"nix", "shell", "compose", "dockerfile"}
    ]


def _wanted(stack: str) -> str:
    return "frontend" if stack in _NODE else "backend"


def _has_source(folder: Path, suffixes: tuple[str, ...], depth: int) -> bool:
    """Whether `folder` holds a file with one of `suffixes`, looking at most `depth` folders down (never into SKIP_DIRS)."""
    entries = sorted(folder.iterdir())
    if any(e.is_file() and e.name.endswith(suffixes) for e in entries):
        return True
    return depth > 1 and any(e.is_dir() and e.name not in SKIP_DIRS and _has_source(e, suffixes, depth - 1) for e in entries)


def _source_folders(repo: Path, suffixes: tuple[str, ...], skip: set[str]) -> list[str]:
    """Root folders (not hidden, not skipped, not repo-level) holding a file with one of `suffixes`, within three levels."""
    return [
        entry.name
        for entry in sorted(repo.iterdir())
        if entry.is_dir()
        and not entry.name.startswith(".")
        and entry.name not in SKIP_DIRS | _REPO_LEVEL | skip
        and _has_source(entry, suffixes, 3)
    ]


def _root_move(ctx: Context, stack: str, taken: set[str]) -> str:
    """The `git mv` that takes a root-level code base into its folder: its manifests and the root folders and files holding its code."""
    target = _wanted(stack)
    files = _NODE_FILES if target == "frontend" else _PYTHON_FILES
    names = [f for f in files if (ctx.repo / f).is_file()]
    if target == "frontend":
        names += sorted(p.name for p in ctx.repo.iterdir() if p.is_file() and p.name.endswith(_NODE_SUFFIXES) and p.name not in names)
    names += _source_folders(ctx.repo, _CODE_SUFFIX[target], taken)
    return f"git mv {' '.join(names)} {target}/"


def judge(ctx: Context) -> Finding:
    """Pass with one code base; with two or more, each must sit in the folder its kind is named for."""
    bases = code_bases(ctx.profile)
    if not bases:
        return not_applicable("no code base detected: there is no layout to judge")
    if len(bases) == 1:
        stack, folder = bases[0]
        return passing(f"one code base ({stack}), at {'the repo root' if folder == '.' else folder + '/'}")
    misplaced = [(s, f) for s, f in bases if f != _wanted(s)]
    if not misplaced:
        return passing("; ".join(f"{s} in {f}/" for s, f in bases))
    taken = {f for _, f in bases if f != "."}
    notes = [f"{s} {'at the repo root' if f == '.' else f'in {f}/'}, not {_wanted(s)}/" for s, f in misplaced]
    moves = [f"git mv {f} {_wanted(s)}" if f != "." else _root_move(ctx, s, taken) for s, f in misplaced]
    return failing(
        f"{len(bases)} code bases ({', '.join(s for s, _ in bases)}) and " + "; ".join(notes),
        "; ".join(moves) + ". Then `uv run blueprint gate render` and fix each path the move breaks; the root keeps the justfile, "
        "AGENTS.md, mise.toml, .blueprint, docs and deploy files",
        FixedBy.OWNER,
    )


check("layout.stacks-in-own-folders", _STATEMENT, layer="stack")(judge)
