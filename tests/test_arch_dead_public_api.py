"""Decay (constitution Article VIII): a name in a package's `__all__` that nothing outside the package uses is a deletion candidate.

A package's public surface is the `__all__` of its top-level `src/<module>/__init__.py`. A name is USED when some file
outside that package's own `src/`, `tests/`, README and CHANGELOG mentions both the name and the package (its module name or
its hyphenated name) in the same file: another package's source or tests, the repo's `tests/`, `tools/`, `skills/`, a
`use-cases/` file, another README, the root `pyproject.toml` (import-linter contracts) or another config. Inside the package,
surfaces count as use: its `__main__.py` files, a `module:name` entry in its own `pyproject.toml` (`[project.scripts]` and
entry-point tables), and the `pytest_*` hooks of a package that registers a `pytest11` plugin.
A name used only by its own package's tests, or only documented in its own README,
is not used by any consumer: it is a hit.

The match is a token match, not an import resolver, so it errs toward "used" (a common word such as `run` next to the package
name counts). Every hit is therefore a real candidate; a miss is possible. Docs, ADRs, the catalog and the ledger are not
consumers and are not read.

A hit is one dead name. This is a report, not a gate: consumers outside this repo (a2kay, a2web, task-loop, ogy) are invisible
to the scan, so most hits are false. Print it with `uv run python tests/test_arch_dead_public_api.py`.
"""

from __future__ import annotations

import ast
import os
import re
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from any_arch import Rule, plant
from any_arch.source import sources

if TYPE_CHECKING:
    from collections.abc import Iterator

    from any_arch import Hit, Source

_ROOT = Path(__file__).resolve().parent.parent

_PRUNE = frozenset(  # dot folders are skipped too: caches, the venv, other worktrees
    {
        "node_modules",
        "__pycache__",
        "docs",
        "catalog",
        "ledger",
        "openspec",
    }
)
_READ = frozenset({".py", ".md", ".toml", ".yaml", ".yml", ".json", ".feature", ".cfg", ".txt", ".sh", ".just"})
_ROOTS = ("packages", "tests", "tools", "skills", "use-cases", "evals")  # where a consumer can live; nothing else is read
_ROOT_FILES = ["pyproject.toml", "README.md", "justfile", "conftest.py"]
_SKIP_NAMES = frozenset({"CHANGELOG.md", "uv.lock"})
_ARCH_FILES = ("tests/test_arch_", "tests/arch_")  # rows and reasons name things without using them
_SKIP_RELS = frozenset({"use-cases/README.md"})  # derived index of the use-cases, not a consumer
_WORD = re.compile(r"\w+")


@cache
def _corpus(root: Path) -> dict[str, tuple[str, frozenset[str]]]:
    """rel path -> (text, its word tokens) of every file a consumer could use a name in."""
    found: dict[str, tuple[str, frozenset[str]]] = {}
    walks = [(str(root), [], [f for f in _ROOT_FILES if (root / f).is_file()])]
    walks += [(folder, dirs, files) for top in _ROOTS for folder, dirs, files in os.walk(root / top)]
    for folder, dirs, files in walks:
        dirs[:] = [d for d in dirs if d not in _PRUNE and not d.startswith(".") and not d.endswith(".egg-info")]
        for name in files:
            path = Path(folder, name)
            if (
                name in _SKIP_NAMES
                or path.relative_to(root).as_posix() in _SKIP_RELS
                or name == Path(__file__).name
                or (path.suffix not in _READ and name != "justfile")
            ):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            found[path.relative_to(root).as_posix()] = (text, frozenset(_WORD.findall(text)))
    return found


def _exports(tree: ast.Module) -> list[ast.Constant]:
    """The string elements of the module's `__all__` list or tuple."""
    for node in tree.body:
        value = node.value if isinstance(node, ast.Assign | ast.AnnAssign) else None
        names = [t.id for t in node.targets if isinstance(t, ast.Name)] if isinstance(node, ast.Assign) else []
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        if "__all__" in names and isinstance(value, ast.List | ast.Tuple):
            return [e for e in value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []


def _uses(root: Path, package: str, module: str, name: str) -> bool:
    own = f"packages/{package}/"
    for rel, (text, tokens) in _corpus(root).items():
        if rel.startswith(own):
            if rel == f"{own}pyproject.toml":
                if re.search(rf"\b{module}[\w.]*:{name}\b", text) or (name.startswith("pytest_") and "entry-points.pytest11" in text):
                    return True  # a script or entry-point target, or a hook of a pytest plugin module
                continue
            if not (rel.startswith(f"{own}src/") and rel.endswith("/__main__.py")):
                continue
        if rel.startswith(_ARCH_FILES):
            if re.search(rf"from {module}(?:\.\w+)* import (?:\([^)]*|[^\n]*)\b{name}\b", text):
                return True  # an arch test lists names in its rows; only an import of the name is use
            continue
        if name in tokens and (module in tokens or package in text):
            return True
    return False


def _dead(root: Path, source: Source) -> Iterator[tuple[str, str, int]]:
    """(package, name, line) of each public name in one `__init__.py` that nothing outside its package uses."""
    match = re.fullmatch(r"packages/([^/]+)/src/([^/]+)/__init__\.py", source.rel)
    if match is None:
        return
    package, module = match.groups()
    for element in _exports(source.tree):
        name = str(element.value)
        if not name.startswith("__") and not _uses(root, package, module, name):
            yield package, name, element.lineno


def _unused(root: Path) -> Rule:
    def find(source: Source) -> Iterator[Hit]:
        for package, _name, line in _dead(root, source):
            yield package, line

    return Rule(
        "dead-public-api",
        "a name in `__all__` that nothing outside its package uses (a report: consumers outside this repo are invisible)",
        find,
        {},
    )


def report(root: Path = _ROOT) -> str:
    """One `package (n): names` line per package with dead names; empty when none. Never a failure."""
    dead: dict[str, list[str]] = {}
    for source in sources(root, ("packages/*/src/*/__init__.py",)):
        for package, name, _line in _dead(root, source):
            dead.setdefault(package, []).append(name)
    return "\n".join(f"{package} ({len(names)}): {', '.join(names)}" for package, names in sorted(dead.items()))


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


_INIT_PATH = "packages/a/src/a/__init__.py"
_INIT = '__all__ = [\n    "dead",\n    "entry",\n    "kept",\n    "main_only",\n    "off_in_readme",\n]\n'


def test_a_planted_name_nothing_outside_the_package_uses_is_a_hit(tmp_path: Path) -> None:
    _write(tmp_path, "packages/b/src/b/m.py", "from a import kept\n")
    _write(tmp_path, "packages/a/tests/test_a.py", "from a import dead\n")  # its own tests are not a consumer
    _write(tmp_path, "packages/a/README.md", "`off_in_readme` and `dead` are documented here\n")
    _write(tmp_path, "packages/a/pyproject.toml", '[project.scripts]\na = "a.cli:entry"\n')
    _write(tmp_path, "packages/a/src/a/__main__.py", "from a import main_only\n")
    assert plant(_unused(tmp_path), tmp_path, _INIT, path=_INIT_PATH) == {"a": [2, 6]}  # `dead` and `off_in_readme`


def test_a_use_in_a_use_case_file_or_another_packages_tests_counts(tmp_path: Path) -> None:
    _write(tmp_path, "use-cases/x--a.toml", 'software = "a"\nneeds = "dead and off_in_readme"\n')
    _write(tmp_path, "packages/b/tests/test_b.py", "import a\na.entry\na.kept\na.main_only\n")
    assert plant(_unused(tmp_path), tmp_path, _INIT, path=_INIT_PATH) == {}


def test_an_arch_test_uses_a_name_only_by_importing_it_and_the_use_case_index_is_no_consumer(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_arch_x.py", "from a import (\n    kept,\n    entry,\n)\n# dead and off_in_readme are named in a row\n")
    _write(tmp_path, "use-cases/README.md", "a: dead, off_in_readme, main_only\n")
    assert plant(_unused(tmp_path), tmp_path, _INIT, path=_INIT_PATH) == {"a": [2, 5, 6]}


@pytest.mark.parametrize(("name", "expected"), [("__version__", {}), ("_private", {"a": [1]})])
def test_a_dunder_is_not_a_public_name(tmp_path: Path, name: str, expected: dict[str, list[int]]) -> None:
    assert plant(_unused(tmp_path), tmp_path, f'__all__ = ["{name}"]\n', path=_INIT_PATH) == expected


def test_the_report_lists_each_package_with_its_dead_names(tmp_path: Path) -> None:
    _write(tmp_path, _INIT_PATH, _INIT)
    _write(tmp_path, "packages/b/src/b/m.py", "from a import kept, entry, main_only\n")
    assert report(tmp_path) == "a (2): dead, off_in_readme"


if __name__ == "__main__":
    print(report())
