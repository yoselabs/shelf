"""Fitness for the `reads` map: a test that names a mapped root file its package is not mapped for.

A static scan, so it holds exactly what text shows. For each mapped root file it looks for the file's path (and, for a glob entry, the
path of each file the glob matches and of the folders holding them) in the text of every package's tests, and of the root conftest and
the plugins it loads (those run in every suite, so a file they read cannot be mapped at all). A test that finds the repo root through
`parents[3]` or more (or four `.parent` in a row) reads the real repo through a path the scan cannot follow, so its package must be mapped
for some file; which ones stays the map's owner's claim. What it cannot see: a path built at run
time (an environment variable, a join of parts, `cwd`), a reader behind a constant defined in another module, and source code the
tests run against the real repo. A reader found that way is the map's owner's to add; the audit narrows the risk, it does not close it.

`audit_repo_tests` does the same for the repo's own tests: each test file must be keyed in `repo-reads`, and every top-level repo path its
source names (a string constant's first segment, an import of a workspace package or of `tools`) must be covered by a pattern of its key.
"""

from __future__ import annotations

import ast
import fnmatch
import re
from typing import TYPE_CHECKING

from any_gate_python.graph import workspace
from any_gate_python.rules import Rules, _glob

if TYPE_CHECKING:
    from pathlib import Path

TEXT = (".py", ".feature", ".toml", ".just", ".json", ".yaml", ".yml", ".txt", ".cfg", ".ini", ".sh")
GENERIC_DIRS = frozenset({".config"})  # a folder every home has: naming it says nothing about the repo's own
_ROOT_HOP = re.compile(r"parents\[\s*([3-9]|\d\d+)\s*\]|(?:\.parent\s*){4,}")


def _texts(folder: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(folder.rglob("*")) if folder.is_dir() else ():
        if path.is_file() and path.suffix in TEXT and "__pycache__" not in path.parts:
            out[path.as_posix()] = path.read_text(encoding="utf-8", errors="replace")  # lossy-ok: detect: a name search, never written back
    return out


def _names(token: str, text: str) -> bool:
    """`text` names `token` as a whole path (`tools.blueprint_fitness` does not name `.blueprint`)."""
    return re.search(rf"(?<![\w.-]){re.escape(token)}(?![\w-])", text) is not None


def _tokens(repo: Path, pattern: str) -> set[str]:
    """What text names the files `pattern` maps: each file's path and each folder above it (no glob characters)."""
    rules = Rules(reads={pattern: ("*",)})
    files = rules.read_files(repo, "*")
    tokens = set(files) or {pattern.rstrip("/")}
    for rel in files:
        parts = rel.split("/")
        tokens.update("/".join(parts[:i]) for i in range(1, len(parts)) if "/".join(parts[:i]) not in GENERIC_DIRS)
    return {t for t in tokens if t}


def _loaded_plugins(repo: Path) -> dict[str, str]:
    """The root conftest and the files of the plugins it names in `pytest_plugins`."""
    conftest = repo / "conftest.py"
    if not conftest.is_file():
        return {}
    text = conftest.read_text(encoding="utf-8")
    found = {"conftest.py": text}
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "pytest_plugins" for t in node.targets):
            for const in ast.walk(node.value):
                if isinstance(const, ast.Constant) and isinstance(const.value, str):
                    module = repo / (const.value.replace(".", "/") + ".py")
                    if module.is_file():
                        found[module.relative_to(repo).as_posix()] = module.read_text(encoding="utf-8")
    return found


def _covered(graph: dict[str, set[str]], readers: tuple[str, ...]) -> set[str]:
    """`readers` and every package depending on them: the suites a change to their file selects."""
    dependents: dict[str, set[str]] = {d: set() for d in graph}
    for d, deps in graph.items():
        for dep in deps:
            dependents[dep].add(d)
    seen, queue = set(readers) & graph.keys(), [*readers]
    while queue:
        for d in dependents.get(queue.pop(), set()) - seen:
            seen.add(d)
            queue.append(d)
    return seen


def _naming(repo: Path, package: str, tokens: set[str], reached: set[str]) -> str | None:
    """The first test of `package` naming one of `tokens` when the file does not select the package, as a problem line."""
    if package in reached:
        return None
    for where, text in _texts(repo / "packages" / package / "tests").items():
        named = next((t for t in sorted(tokens) if _names(t, text)), None)
        if named:
            return f"{where} names {named}, but {package!r} is not mapped for it (nor depends on a mapped package)"
    return None


def audit(repo: Path, rules: Rules | None = None) -> list[str]:
    """What is wrong with the `reads` map, one line each; empty when every test that names a mapped file is covered by it."""
    rules = rules or Rules.load(repo)
    graph, _ = workspace(repo)
    problems: list[str] = []
    plugin_text = _loaded_plugins(repo)
    for pattern, readers in sorted(rules.reads.items()):
        problems += [f"{pattern}: reader {name!r} is not a package" for name in readers if name not in graph]
        tokens = _tokens(repo, pattern)
        problems += [
            f"{pattern}: read by {where}, which loads into every suite: it cannot be mapped"
            for where, text in plugin_text.items()
            if any(_names(t, text) for t in tokens)
        ]
        reached = _covered(graph, readers)
        problems += [f"{pattern}: {found}" for package in sorted(graph) if (found := _naming(repo, package, tokens, reached))]
    mapped_anywhere = {n for names in rules.reads.values() for n in names}
    for package in sorted(graph.keys() - mapped_anywhere):
        for where, text in _texts(repo / "packages" / package / "tests").items():
            if _ROOT_HOP.search(text):
                problems.append(f"{where} finds the repo root (parents[3] or deeper), but {package!r} is mapped for no root file")
                break
    return problems


_SKIPPED_TOPS = frozenset(
    {".git", ".venv", ".pytest_cache", ".ruff_cache", ".hypothesis", ".import_linter_cache", ".coverage", "node_modules"}
)
_PACKAGE_PARTS = {"tests": "tests", "bench": "bench"}  # a constant under `packages/`: the folder a package keeps beside `src`
_PACKAGE_FILES = ("README.md", "CHANGELOG.md", "pyproject.toml")


def _probes(repo: Path, source: str) -> set[str]:
    """Paths standing for what `source` (one repo test) names: one invented path under each top-level folder or file it mentions."""
    tops = {entry.name for entry in sorted(repo.iterdir())} - _SKIPPED_TOPS
    modules = {m.name for m in sorted(repo.glob("packages/*/src/*")) if m.is_dir()}
    constants: set[str] = set()
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            constants.add(node.value)
            top = re.split(r"[/\\]", node.value)[0]
            if top in tops:
                found.add(top)
            continue
        if isinstance(node, ast.Import):
            heads = {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            heads = {node.module.split(".")[0]}
        else:
            continue
        found.update("packages" for h in heads if h in modules)
        found.update("tools" for h in heads if h == "tools")
    probes = {_probe(repo, top) for top in found}
    if "packages" in found:
        probes.update(
            f"packages/x/{part}/x.py" for part, name in _PACKAGE_PARTS.items() if any(name in re.split(r"[/\\]", c) for c in constants)
        )
        probes.update(f"packages/x/{name}" for name in _PACKAGE_FILES if name in constants)
    return probes


def _probe(repo: Path, top: str) -> str:
    if top == "packages":
        return "packages/x/src/x.py"
    return f"{top}/x.py" if (repo / top).is_dir() else top


def audit_repo_tests(repo: Path, rules: Rules | None = None) -> list[str]:
    """What is wrong with the `repo-reads` keys: a test file not keyed, or one reading a path no pattern of its key covers."""
    rules = rules or Rules.load(repo)
    if not rules.repo_tests:
        return []
    problems: list[str] = []
    for test in sorted((repo / rules.repo_tests).glob("test_*.py")):
        patterns = [p for key, paths in rules.repo_reads.items() if key == "*" or fnmatch.fnmatchcase(test.name, key) for p in paths]
        if not rules.keyed(test.name):
            problems.append(f"{test.name} is not keyed in [tool.any-gate.python.repo-reads]: it runs on every change")
            continue
        uncovered = [
            probe
            for probe in sorted(_probes(repo, test.read_text(encoding="utf-8")))
            if not any(_glob(probe, p.removeprefix("!")) for p in patterns)
        ]
        problems.extend(
            f"{test.name} names {probe.split('/')[0]!r} ({probe}), which no pattern of its repo-reads key covers" for probe in uncovered
        )
    return problems
