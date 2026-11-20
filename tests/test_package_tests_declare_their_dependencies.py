"""A package's tests run in isolation only if the package declares what they import (shelf-wctp.4, task 8 of gate-test-loop).

`atomic-io` failed collection alone because its tests import `pytest_bdd` and nothing in its `pyproject.toml` named it: the shared dev
environment hid that. Two things make an isolated run (`uv run --isolated --package X --group dev pytest packages/X/tests`) work:

- every third-party module the package's tests import belongs to a distribution the package declares (its dependencies or its `dev`
  group; an extra is not installed by an isolated run);
- every package's dev group carries what the root `conftest.py` and the root pytest settings need to load at all (`hypothesis`, pytest and
  pytest-asyncio for `asyncio_mode`), since pytest reads the root configuration for every suite.

An import whose distribution is not installed here (an opt-in engine such as `patchright`) cannot be mapped and is not judged.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from importlib.metadata import packages_distributions
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# What every isolated run needs before its first test: the root conftest imports hypothesis, the root pytest settings name pytest-asyncio.
BASELINE = ("pytest", "pytest-asyncio", "hypothesis")


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _name(requirement: str) -> str:
    return _norm(re.split(r"[\[<>=!~; ]", requirement.strip(), maxsplit=1)[0])


def _groups(pyproject: Path) -> dict[str, set[str]]:
    """Declared distribution names by place: `dependencies`, `extras`, and each dependency group."""
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data.get("project", {})
    found = {"dependencies": {_name(r) for r in project.get("dependencies", [])}}
    found["extras"] = {_name(r) for reqs in project.get("optional-dependencies", {}).values() for r in reqs}
    for group, reqs in data.get("dependency-groups", {}).items():
        found[f"group:{group}"] = {_name(r) for r in reqs if isinstance(r, str)}
    return found


def _declared(pyproject: Path) -> set[str]:
    """What an isolated run installs: the dependencies and the `dev` group. An extra is not installed by `--group dev`, so none counts."""
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    groups = _groups(pyproject)
    declared = groups["dependencies"] | groups.get("group:dev", set())
    own = _norm(data.get("project", {}).get("name", ""))
    for requirement in data.get("dependency-groups", {}).get("dev", []):
        if isinstance(requirement, str) and _name(requirement) == own and "[" in requirement:  # `self[extra]` installs that extra
            for extra in requirement.split("[", 1)[1].split("]", 1)[0].split(","):
                declared |= {_name(r) for r in data.get("project", {}).get("optional-dependencies", {}).get(extra.strip(), [])}
    return declared


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


def _workspace_modules(repo: Path) -> set[str]:
    return {entry.stem for src in repo.glob("packages/*/src") for entry in src.iterdir() if entry.is_dir() or entry.suffix == ".py"}


def undeclared_imports(repo: Path) -> list[str]:
    """One line per `package's tests import module (distribution) it does not declare`."""
    distributions = packages_distributions()
    workspace = _workspace_modules(repo)
    found: set[str] = set()
    for package in sorted(repo.glob("packages/*")):
        tests = package / "tests"
        if not tests.is_dir():
            continue
        declared = _declared(package / "pyproject.toml")
        for source in sorted(tests.rglob("*.py")):
            for module in _imported(source):
                local = (tests / module).exists() or (tests / f"{module}.py").exists()
                if module in sys.stdlib_module_names or module in workspace or module in {"tests", "conftest"} or local:
                    continue
                owners = {_norm(d) for d in distributions.get(module, [])}
                if owners and not owners & declared:
                    found.add(f"{package.name} tests import {module} ({'/'.join(sorted(owners))}) without declaring it")
    return sorted(found)


def missing_baseline(repo: Path) -> list[str]:
    """One line per package whose dev group lacks a piece of the baseline."""
    found: list[str] = []
    for package in sorted(repo.glob("packages/*")):
        if not (package / "tests").is_dir():
            continue
        dev = _groups(package / "pyproject.toml").get("group:dev", set())
        found.extend(f"{package.name} dev group lacks {need}" for need in BASELINE if need not in dev)
    return found


def test_every_third_party_import_in_a_packages_tests_is_declared_by_that_package() -> None:
    assert undeclared_imports(ROOT) == [], (
        "declare it in the package's own pyproject.toml (the `dev` dependency group for test-only libraries)"
    )


def test_every_packages_dev_group_carries_what_the_root_pytest_configuration_needs() -> None:
    assert missing_baseline(ROOT) == [], (
        f"each package's `dev` group lists {', '.join(BASELINE)}: the root conftest and settings load for every suite"
    )


def test_the_check_sees_a_missing_declaration_and_a_missing_baseline(tmp_path: Path) -> None:
    pkg = tmp_path / "packages" / "demo"
    (pkg / "tests").mkdir(parents=True)
    (pkg / "src" / "demo").mkdir(parents=True)
    (pkg / "tests" / "test_x.py").write_text("import hypothesis\nimport pytest\n", encoding="utf-8")
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0"\n[dependency-groups]\ndev = ["pytest>=8"]\n', encoding="utf-8"
    )
    assert undeclared_imports(tmp_path) == ["demo tests import hypothesis (hypothesis) without declaring it"]
    assert missing_baseline(tmp_path) == ["demo dev group lacks pytest-asyncio", "demo dev group lacks hypothesis"]
