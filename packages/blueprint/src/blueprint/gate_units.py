"""Test units for a repo that is not a uv workspace: what each unit's tests reach, and the key it passed under.

A workspace is planned by any-gate-python (`packages/*`). A repo with one package and many test folders declares its units in
`pyproject.toml`; the plan is then `path<TAB>key` per unit path, the same shape, so any-gate skips a unit whose key already passed.

    [tool.blueprint.test]
    coverage = "coverage"          # or "pytest-cov"; absent: no coverage measured, no floor
    floor = 90                     # whole-repo percent; combined from every unit's cached data, so a skipped unit still counts

    [tool.blueprint.test.units.ui]
    paths = ["tests/ui"]           # a path, or a glob (`tests/test_*.py`): every match, sorted
    reads = ["src/app/ui/**"]      # files the tests read that no import names (JS run under node, fixtures, templates)

    [tool.blueprint.test.units.root]
    rest = true                    # every test file and folder under the test roots no other unit claims: a new file joins it

A unit's key hashes: every file under its paths, every first-party module its Python files import (transitively, found by reading
the imports), the `conftest.py` of each folder above its paths, the files its `reads` globs match, `uv.lock`, and the parts of
`pyproject.toml` a test run can see. A change to shared code therefore changes the key of every unit that reaches it. It fails closed
where the reading is blind: a file beside reached code (a template, SQL, JS) changes the key, and a module imported by a computed name
(`importlib.import_module(name)`) widens it to its whole package. A data file in another folder is the one gap: name it in `reads`.
"""

from __future__ import annotations

import ast
import configparser
import hashlib
import json
import shlex
import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

COVERAGE_MODES = ("coverage", "pytest-cov")
_SOURCE_ROOTS = ("", "src")
_SKIP_PARTS = frozenset({"__pycache__", ".venv", "node_modules", ".git"})
_NOT_INPUTS = frozenset({".py", ".pyc", ".pyo", ".DS_Store", ".swp"})  # beside reached code, but never an input to it


@dataclass(frozen=True)
class Unit:
    name: str
    paths: tuple[str, ...]
    reads: tuple[str, ...] = ()


@dataclass(frozen=True)
class Config:
    units: tuple[Unit, ...]
    coverage: str = ""
    floor: float | None = None
    pytest_args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    marks: str = ""
    problems: tuple[str, ...] = ()
    test_roots: tuple[str, ...] = ("tests",)

    def arguments(self) -> list[str]:
        return [*self.pytest_args, *(["-m", self.marks] if self.marks else [])]

    def every_mark(self) -> list[str]:
        """The configured pytest arguments without the mark expression: the release run runs every mark."""
        return list(self.pytest_args)

    def unit_of(self, path: str) -> Unit | None:
        return next((u for u in self.units if path in u.paths), None)


def load(repo: Path) -> Config | None:
    """The declared units or their validation problems; None when the repo declares none."""
    config = read_config(repo)
    return config if config.units or config.problems else None


def read_config(repo: Path) -> Config:
    """Test settings, including repos with no declared units; invalid unit paths remain visible as problems."""
    manifest = repo / "pyproject.toml"
    if not manifest.is_file():
        return Config(())
    try:
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return Config(())
    table: dict[str, Any] = data.get("tool", {}).get("blueprint", {}).get("test", {})  # Any: parsed TOML
    roots = _unit_test_roots(repo, data)
    units, problems = _declared_units(repo, table.get("units", {}), roots)
    mode = table.get("coverage", "")
    floor = table.get("floor")
    args = table.get("pytest-args", [])
    env = table.get("env", {})
    marks = table.get("marks", "")
    return Config(
        tuple(units),
        mode if mode in COVERAGE_MODES else "",
        float(floor) if isinstance(floor, int | float) else None,
        tuple(args) if isinstance(args, list) and all(isinstance(arg, str) for arg in args) else (),
        dict(env) if isinstance(env, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()) else {},
        marks if isinstance(marks, str) else "",
        tuple(problems),
        roots,
    )


def _has_glob(path: str) -> bool:
    return any(c in path for c in "*?[")


def _glob_paths(repo: Path, name: str, paths: list[str], problems: list[str]) -> list[str]:
    """`paths` with each glob replaced by what it matches (repo-relative, sorted when any glob was used); no match is a problem."""
    out: list[str] = []
    for path in paths:
        if not _has_glob(path):
            out.append(path)
            continue
        found = [p.relative_to(repo).as_posix() for p in sorted(repo.glob(path))]
        found = [rel for rel in found if not _SKIP_PARTS & set(rel.split("/"))]
        if found:
            out += found
        else:
            problems.append(f"unit {name}: `{path}` matches nothing")
    unique = list(dict.fromkeys(out))
    return sorted(unique) if any(_has_glob(p) for p in paths) else unique


def _is_test_file(path: Path) -> bool:
    return path.suffix == ".py" and (path.name.startswith("test_") or path.stem.endswith("_test"))


def _unclaimed(repo: Path, roots: tuple[str, ...], claimed: set[str]) -> list[str]:
    """The test files and folders under `roots` that `claimed` does not name or contain (a folder whole, unless a unit names part)."""
    found: set[str] = set()

    def walk(directory: Path) -> None:
        for child in sorted(directory.iterdir()):
            rel = child.relative_to(repo).as_posix()
            if _SKIP_PARTS & set(child.relative_to(repo).parts) or any(rel == c or rel.startswith(c + "/") for c in claimed):
                continue
            if child.is_file():
                if _is_test_file(child):
                    found.add(rel)
            elif any(c.startswith(rel + "/") for c in claimed):
                walk(child)  # a unit names something inside: the rest of it is still unclaimed
            elif any(_is_test_file(f) and not _SKIP_PARTS & set(f.relative_to(repo).parts) for f in sorted(child.rglob("*.py"))):
                found.add(rel)

    for root in roots:
        if (repo / root).is_dir():
            walk(repo / root)
    return sorted(found)


def _declared_units(repo: Path, raw_units: dict[str, Any], roots: tuple[str, ...]) -> tuple[list[Unit], list[str]]:  # Any: parsed TOML
    """The units `[tool.blueprint.test.units]` declares, globs expanded to concrete paths, and the problems found.

    A unit with `rest = true` also owns every test file and folder under the test roots that no other unit claims, so a new test file is
    covered without editing the table. Only one such unit is allowed; with nothing left unclaimed it is no unit.
    """
    problems: list[str] = []
    units: list[Unit] = []
    rest_name = ""
    rest_paths: list[str] = []
    for name, spec in sorted(raw_units.items()):
        is_rest = isinstance(spec, dict) and spec.get("rest") is True
        paths = spec.get("paths", [] if is_rest else None) if isinstance(spec, dict) else None
        if not isinstance(paths, list) or (not paths and not is_rest) or not all(isinstance(p, str) and p for p in paths):
            problems.append(f"unit {name}: paths must be a non-empty list of paths")
            continue
        expanded = _glob_paths(repo, name, paths, problems)
        if is_rest and rest_name:
            problems.append(f"unit {name}: only one unit may be `rest = true` (already {rest_name})")
        elif is_rest:
            rest_name, rest_paths = name, expanded
        else:
            units.append(Unit(name, tuple(expanded), tuple(spec.get("reads", ()))))
    if rest_name:
        claimed = {p for u in units for p in u.paths} | set(rest_paths)
        owned = sorted({*rest_paths, *_unclaimed(repo, roots, claimed)})
        if owned:
            spec = raw_units[rest_name]
            units.append(Unit(rest_name, tuple(owned), tuple(spec.get("reads", ()))))
    return sorted(units, key=lambda u: u.name), problems


def _unit_test_roots(repo: Path, data: dict[str, Any]) -> tuple[str, ...]:
    """The configured pytest roots; the conventional tests folder is checked too."""
    roots = data.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("testpaths", [])
    if isinstance(roots, str):
        roots = shlex.split(roots)
    for name, section in (("pytest.ini", "pytest"), ("tox.ini", "pytest"), ("setup.cfg", "tool:pytest")):
        if (repo / name).is_file():
            parser = configparser.ConfigParser(interpolation=None)
            parser.read(repo / name)
            roots = shlex.split(parser.get(section, "testpaths", fallback="")) or roots
            break
    return tuple(dict.fromkeys(["tests", *roots]))


def uncovered_test_folders(repo: Path, config: Config) -> list[str]:
    """Folders containing conventional pytest files outside every declared unit, without collecting tests."""
    paths = [repo / path for unit in config.units for path in unit.paths]
    return sorted(
        {
            file.parent.relative_to(repo).as_posix()
            for root in config.test_roots
            for pattern in ("test_*.py", "*_test.py")
            for file in (repo / root).rglob(pattern)
            if file.is_file()
            and not _SKIP_PARTS & set(file.relative_to(repo).parts)
            and not any(file == path or file.is_relative_to(path) for path in paths)
        }
    )


class Reader:
    """Reads each file once for a whole run: its bytes (hashed), and what parsing them says (imports, computed imports).

    A file's bytes are read once however many units reach it, and parsed from those same bytes; the key hashes the same bytes it always did.
    """

    def __init__(self) -> None:
        self._bytes: dict[Path, bytes] = {}
        self._parsed: dict[Path, tuple[tuple[tuple[str, ...], ...], bool]] = {}
        self._project: dict[Path, str] = {}

    def data(self, file: Path) -> bytes:
        if file not in self._bytes:
            self._bytes[file] = file.read_bytes()
        return self._bytes[file]

    def parsed(self, repo: Path, file: Path) -> tuple[tuple[tuple[str, ...], ...], bool]:
        """`(the dotted names the file imports, whether it imports by a computed name)`; empty and False when it cannot be parsed."""
        if file not in self._parsed:
            try:
                tree = ast.parse(self.data(file).decode("utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
                self._parsed[file] = ((), False)
            else:
                self._parsed[file] = (tuple(tuple(n) for n in _import_names(repo, file, tree)), _computes_imports(tree))
        return self._parsed[file]

    def project(self, repo: Path, config: Config) -> str:
        if repo not in self._project:
            self._project[repo] = _project_part(repo, config, self)
        return self._project[repo]


def _files(repo: Path, rel: str) -> list[Path]:
    root = repo / rel
    if root.is_file():
        return [root]
    return sorted(p for p in root.rglob("*") if p.is_file() and not _SKIP_PARTS & set(p.relative_to(repo).parts))


def _module_file(repo: Path, parts: list[str]) -> Path | None:
    for base in _SOURCE_ROOTS:
        root = repo / base if base else repo
        as_file = root.joinpath(*parts).with_suffix(".py")
        if as_file.is_file():
            return as_file
        as_package = root.joinpath(*parts, "__init__.py")
        if as_package.is_file():
            return as_package
    return None


def _initializers(repo: Path, module: Path) -> list[Path]:
    """The `__init__.py` of every folder above `module` (they run when it is imported)."""
    found = []
    for parent in module.parents:
        if parent == repo or repo not in parent.parents:
            break
        if (parent / "__init__.py").is_file():
            found.append(parent / "__init__.py")
    return found


def _import_names(repo: Path, file: Path, tree: ast.AST) -> list[list[str]]:
    """The dotted module names `file` imports, absolute, as lists of parts (a `from x import y` also tries `x.y`)."""
    package = file.relative_to(repo).with_suffix("").parts[:-1]
    if package and package[0] == "src":
        package = package[1:]
    names: list[list[str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name.split(".") for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = list(package[: len(package) - node.level + 1]) if node.level else []
            if node.level and node.level > len(package) + 1:
                continue
            head = base + (node.module.split(".") if node.module else [])
            names.append(head)
            names += [[*head, alias.name] for alias in node.names if alias.name != "*"]
    return names


def reached(repo: Path, starts: list[Path], reader: Reader | None = None) -> set[Path]:
    """Every first-party Python file the `starts` import, transitively, with the `__init__.py` files above them."""
    reader = reader or Reader()
    seen: set[Path] = set()
    queue = list(starts)
    while queue:
        file = queue.pop()
        if file in seen or file.suffix != ".py":
            continue
        seen.add(file)
        for parts in reader.parsed(repo, file)[0]:
            target = _module_file(repo, list(parts))
            if target is not None:
                queue += [target, *_initializers(repo, target)]
    return seen


def _computes_imports(tree: ast.AST) -> bool:
    """Whether the file imports by a computed name (`importlib.import_module(name)`, `__import__(name)`): no import graph sees it."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
        if target in {"import_module", "__import__"} and not (node.args and isinstance(node.args[0], ast.Constant)):
            return True
    return False


def _top_package(repo: Path, file: Path) -> Path:
    """The folder of the top-level package `file` belongs to (`src/app` for `src/app/ui/view.py`)."""
    rel = file.relative_to(repo).parts
    depth = 2 if rel[0] == "src" and len(rel) > 2 else 1
    return repo.joinpath(*rel[:depth]) if len(rel) > depth else file.parent


def _project_part(repo: Path, config: Config, reader: Reader) -> str:
    """What of `pyproject.toml` a test run can see: dependencies and how pytest and coverage run (lint and type config never)."""
    try:
        data = tomllib.loads(reader.data(repo / "pyproject.toml").decode("utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return ""
    tool = data.get("tool", {})
    seen = {
        "project": data.get("project", {}),
        "groups": data.get("dependency-groups", {}),
        "pytest": {k: v for k, v in tool.get("pytest", {}).get("ini_options", {}).items() if k != "testpaths"},
        "coverage": tool.get("coverage", {}),
        "uv": tool.get("uv", {}),
    }
    seen["blueprint-test"] = {"pytest-args": config.pytest_args, "env": config.env, "marks": config.marks}
    return json.dumps(seen, sort_keys=True, default=repr)


def keys(repo: Path, config: Config) -> dict[str, str]:
    """The key of every unit, by name: one run's worth, each file read once however many units reach it."""
    reader = Reader()
    return {unit.name: key(repo, unit, reader, config) for unit in config.units}


def key(repo: Path, unit: Unit, reader: Reader | None = None, config: Config | None = None) -> str:
    """The hash of everything `unit`'s tests can see (see the module doc)."""
    reader = reader or Reader()
    config = config or read_config(repo)
    own = [f for p in unit.paths for f in _files(repo, p)]
    folders = {repo, *(d for p in unit.paths for d in [repo / p, *(repo / p).parents] if d == repo or repo in d.parents)}
    starts = [*own, *(d / name for d in sorted(folders) for name in ("conftest.py", "__init__.py") if (d / name).is_file())]
    read = sorted(f for glob in unit.reads for f in repo.glob(glob) if f.is_file())
    code = reached(repo, starts, reader)
    # Fail closed where the import graph cannot see: files that sit beside reached code (templates, SQL, JS) change the key, and a
    # module imported by a computed name widens it to its whole package.
    beside = sorted(
        f
        for py in sorted(code - set(starts))
        for f in py.parent.iterdir()
        if f.is_file() and f.suffix not in _NOT_INPUTS and f.name not in _NOT_INPUTS
    )
    wide = {f for py in code if reader.parsed(repo, py)[1] for f in _files(repo, _top_package(repo, py).relative_to(repo).as_posix())}
    files = sorted({*starts, *code, *read, *beside, *wide})
    digest = hashlib.sha256()
    for file in files:
        digest.update(file.relative_to(repo).as_posix().encode())
        digest.update(b"\0")
        digest.update(reader.data(file))
    for rel in ("uv.lock", "pytest.ini", ".coveragerc", "setup.cfg", "tox.ini", ".python-version"):
        if (repo / rel).is_file():
            digest.update(rel.encode())
            digest.update(reader.data(repo / rel))
    digest.update(reader.project(repo, config).encode())
    return digest.hexdigest()[:32]


def plan(repo: Path, config: Config, *, cached: set[str] | None = None, unit_keys: dict[str, str] | None = None) -> str:
    """`path<TAB>key` per unit path.

    With `cached` (the `unit:key` names whose coverage data exists) the data is the receipt: a unit with data is left out of the
    plan, and one without is listed with no key (it runs, and its data is then the proof). A receipt there would be one more thing
    to keep true: any-gate records none for a blank key, so a unit would run twice before it was skipped.
    """
    unit_keys = unit_keys if unit_keys is not None else keys(repo, config)
    lines: list[str] = []
    for unit in config.units:
        unit_key = unit_keys[unit.name]
        if cached is None:
            lines += [f"{path}\t{unit_key}\n" for path in unit.paths]
        elif f"{unit.name}:{unit_key}" not in cached:
            lines += [f"{path}\t\n" for path in unit.paths]
    return "".join(lines)
