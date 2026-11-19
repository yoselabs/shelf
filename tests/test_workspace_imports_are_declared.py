"""Affected-only tests are exact only if every workspace import is a declared dependency (shelf-wctp).

`tools/affected.py` walks each package's declared dependencies, optional dependencies and dependency groups. A package whose source or tests
import another workspace package without declaring it is never re-tested when that package changes. A mutation of `atomic-io` on
2026-11-19 showed the class of miss; `mcp-bridge` and `mcp-call` imported `async-scope` in their tests undeclared.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import affected

ROOT = Path(__file__).resolve().parent.parent


def _module_owners(repo: Path) -> dict[str, str]:
    """Top-level import name -> the workspace package directory that provides it."""
    owners: dict[str, str] = {}
    for src in sorted(repo.glob("packages/*/src")):
        for entry in src.iterdir():
            if entry.is_dir() or entry.suffix == ".py":
                owners[entry.stem] = src.parent.name
    return owners


def _imported(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def undeclared(repo: Path) -> list[str]:
    """One line per `package imports other` pair the package does not declare."""
    graph, _plugins = affected.workspace(repo)
    owners = _module_owners(repo)
    found: set[str] = set()
    for package, declared in graph.items():
        for folder in ("src", "tests"):
            for source in sorted((repo / "packages" / package / folder).rglob("*.py")):
                for name in _imported(source):
                    owner = owners.get(name)
                    if owner and owner != package and owner not in declared:
                        found.add(f"{package} ({folder}) imports {owner} without declaring it")
    return sorted(found)


def test_every_workspace_import_is_a_declared_dependency() -> None:
    assert undeclared(ROOT) == [], (
        "declare the dependency (dependencies, or a dependency group for tests) in the importing package's pyproject.toml"
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for name, deps in (("base", ""), ("top", '"base>=0"')):
        package = tmp_path / "packages" / name
        (package / "src" / name).mkdir(parents=True)
        (package / "src" / name / "__init__.py").write_text("")
        (package / "tests").mkdir()
        (package / "pyproject.toml").write_text(f'[project]\nname = "{name}"\ndependencies = [{deps}]\n')
    return tmp_path


def test_an_undeclared_import_in_tests_is_reported(repo: Path) -> None:
    (repo / "packages/base/tests/test_x.py").write_text("import top\n")
    assert undeclared(repo) == ["base (tests) imports top without declaring it"]


def test_a_declared_import_and_a_stdlib_import_pass(repo: Path) -> None:
    (repo / "packages/top/src/top/__init__.py").write_text("import base\nimport os\n")
    assert undeclared(repo) == []
