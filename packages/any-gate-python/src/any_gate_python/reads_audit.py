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


def _literals(source: str) -> str:
    """The string constants of Python `source` that are not docstrings, one per line."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""
    docs = {
        id(n.body[0].value)
        for n in ast.walk(tree)
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
    }
    return "\n".join(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs)


def _reads_by(repo: Path, package: str, tokens: set[str]) -> str | None:
    """The first Python test of `package` holding a string that names one of `tokens`, as a problem line.

    Only a package whose tests find the repo root (`parents[3]` or deeper) can read the real repo; a name in the tests of one that cannot
    is a file the test writes into its own temp tree.
    """
    texts = {where: text for where, text in _texts(repo / "packages" / package / "tests").items() if where.endswith(".py")}
    if not any(_ROOT_HOP.search(text) for text in texts.values()):
        return None
    for where, text in texts.items():
        literals = _literals(text)
        named = next((t for t in sorted(tokens) if _names(t, literals)), None)
        if named:
            return f"{where} names {named}, but a change there selects no suite (no-effect)"
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
    for token_source in rules.no_effect:
        # `no-effect` says no suite reads the path; a package test naming it is a suite that would be skipped when it changes
        # Only a whole file's path counts as naming it, and only in a string a test runs (not a comment or docstring: "see docs/x.md").
        # A root file by its bare name (`README.md`) is what a test writes into its own temp repo: only a path below a folder counts.
        tokens = {t for t in Rules(reads={token_source: ("*",)}).read_files(repo, "*") if "/" in t}
        problems += [f"no-effect {token_source}: {found}" for package in sorted(graph) if (found := _reads_by(repo, package, tokens))]
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
    tree = ast.parse(source)
    names = _named_names(tree)
    walks = any(_unnamed_walk(node, names) for node in ast.walk(tree))
    for node in ast.walk(tree):
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
    if walks:
        probes.add(WALK)
    if "packages" in found:
        probes.update(
            f"packages/x/{part}/x.py" for part, name in _PACKAGE_PARTS.items() if any(name in re.split(r"[/\\]", c) for c in constants)
        )
        probes.update(f"packages/x/{name}" for name in _PACKAGE_FILES if name in constants)
    return probes


WALK = "(a walk of the repo)"  # what an unnamed `rglob`/`iterdir`/`os.walk` reads: only a `*` (or `!*`) pattern covers it
_WALKERS = frozenset({"rglob", "glob", "iterdir", "scandir"})


def _named(node: ast.AST, names: frozenset[str] = frozenset()) -> bool:
    """`node` holds a string constant, or a name assigned one (`DOCS = ROOT / "docs"`)."""
    return any(
        (isinstance(n, ast.Constant) and isinstance(n.value, str)) or (isinstance(n, ast.Name) and n.id in names) for n in ast.walk(node)
    )


def _named_names(tree: ast.AST) -> frozenset[str]:
    """Names the module binds to an expression holding a string constant (an assignment, a loop or comprehension over one): a walk from
    one still names a path."""
    # A parameter takes the path its caller names (the module's constants), and a `tmp_path` is the test's own folder.
    found: set[str] = {a.arg for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for a in n.args.args}
    found |= {"tmp_path", "tmp_path_factory", "tmpdir"}
    for _ in range(3):  # a loop variable over a name bound above it: a few passes settle the chain
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and _named(node.value, frozenset(found)):
                found.update(t.id for t in node.targets if isinstance(t, ast.Name))
            elif isinstance(node, (ast.For, ast.comprehension)) and _named(node.iter, frozenset(found)):
                found.update(n.id for n in ast.walk(node.target) if isinstance(n, ast.Name))
    return frozenset(found)


def _pattern_names_a_path(call: ast.Call) -> bool:
    """A `glob`/`rglob` pattern that starts with a literal folder (`packages/*/src`) names where it looks."""
    first = call.args[0] if call.args else None
    return isinstance(first, ast.Constant) and isinstance(first.value, str) and "/" in first.value and first.value[0] not in "*?[/"


def _unnamed_walk(node: ast.AST, names: frozenset[str]) -> bool:
    """A call listing a folder whose own path names no string (`ROOT.rglob(...)`, `repo.iterdir()`, `os.walk(root)`)."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in _WALKERS:
        return not _named(func.value, names) and not _pattern_names_a_path(node)
    if isinstance(func, ast.Attribute) and func.attr == "walk" and isinstance(func.value, ast.Name) and func.value.id == "os":
        return not any(_named(arg, names) for arg in node.args)
    return False


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
    for test in sorted((repo / rules.repo_tests).rglob("test_*.py")):
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
            f"{test.name} walks the repo without naming a path ({probe}): key it `*` (reads all) or `!*` (declared not read)"
            if probe == WALK
            else f"{test.name} names {probe.split('/')[0]!r} ({probe}), which no pattern of its repo-reads key covers"
            for probe in uncovered
        )
    return problems
