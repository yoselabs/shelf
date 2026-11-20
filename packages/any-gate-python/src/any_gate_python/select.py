"""The suites a change reaches, and the key each passed under.

A change selects the packages it touches and, through the workspace graph, every package depending on them. A change anywhere the graph
cannot see (an unknown path, or a pytest plugin package that loads into every run) selects every package. Never a silent pass.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from any_gate.plan import too_wide
from stream_proc import capture

from any_gate_python.graph import (
    LOCK_FILES,
    Exporter,
    ExportError,
    extract_base,
    package_exports,
    root_config,
    touched_between,
    workspace,
)
from any_gate_python.rules import Rules, matches

if TYPE_CHECKING:
    from collections.abc import Callable

GIT_TIMEOUT = 600.0  # seconds one git call may take


def _fitness(repo: Path, changed: list[str], rules: Rules) -> list[str]:
    """The repo's own tests: whole when a gated test's input changed, else each file but the gated ones a change misses."""
    if not rules.repo_tests:
        return []
    root = rules.repo_tests
    if any(matches(p, rules.gated_inputs) for p in changed):
        return [root]

    def runs(name: str) -> bool:
        reads = (f"{root}/{name}", *rules.gated_reads.get(name, ()))
        return not rules.is_gated(name) or any(p.startswith(reads) for p in changed)

    files = [p.relative_to(repo).as_posix() for p in sorted((repo / root).glob("test_*.py")) if runs(p.name)]
    return files or [root]


def affected_packages(
    repo: Path, changed: list[str], lock: Callable[[], set[str] | None] | None = None, rules: Rules | None = None
) -> set[str]:
    """The package directories `changed` reaches: the changed ones and, through the graph, everything depending on them.

    `lock` answers which packages the lock files changed for (see `lock_touched`); without it a lock change selects everything.
    """
    rules = rules or Rules.load(repo)
    graph, plugins = workspace(repo)
    every = sorted(graph)
    touched: set[str] = set()
    from_lock: set[str] | None = None
    asked = False
    for path in changed:
        parts = path.split("/")
        if parts[0] == "packages" and len(parts) > 2 and parts[1] in graph:
            touched.add(parts[1])
        elif not rules.observable(path):
            continue
        elif path in LOCK_FILES and lock is not None:
            if not asked:
                from_lock, asked = lock(), True
            touched.update(every if from_lock is None else from_lock & graph.keys())
        else:
            touched.update(every)
    if touched & plugins:
        touched.update(every)

    dependents: dict[str, set[str]] = {d: set() for d in graph}
    for d, deps in graph.items():
        for dep in deps:
            dependents[dep].add(d)
    queue, seen = list(touched), set(touched)
    while queue:
        for d in dependents[queue.pop()] - seen:
            seen.add(d)
            queue.append(d)
    return seen


def affected(repo: Path, changed: list[str], lock: Callable[[], set[str] | None] | None = None, rules: Rules | None = None) -> list[str]:
    """The pytest paths to run for `changed` (repo-relative paths)."""
    rules = rules or Rules.load(repo)
    seen = affected_packages(repo, changed, lock, rules)
    tests = (f"packages/{d}/tests" for d in sorted(seen) if (repo / "packages" / d / "tests").is_dir())
    return [*_fitness(repo, changed, rules), *tests]


def reach(repo: Path, count: int, exporter: Exporter = package_exports) -> list[tuple[str, int, int]]:
    """For each of the last `count` first-parent commits: `(short sha, changed files, package suites it reaches)`.

    The selection a commit would have had: the same rules, the lock read against the commit's parent. A measure of how wide the
    gate runs, so a rule that quietly widens it (a lock rule once selected every package for 45 of 50 commits) shows up.
    """
    rows: list[tuple[str, int, int]] = []
    for sha in _git(repo, "log", "--first-parent", f"-{count}", "--format=%h").split():
        changed = _git(repo, "diff", "--name-only", f"{sha}^", sha).splitlines()
        with tempfile.TemporaryDirectory() as old, tempfile.TemporaryDirectory() as new:
            try:
                extract_base(repo, f"{sha}^", Path(old))
                extract_base(repo, sha, Path(new))
            except ExportError:
                continue
            reached = affected_packages(Path(new), changed, lambda: touched_between(Path(old), Path(new), exporter))
        rows.append((sha, len(changed), len(reached)))
    return rows


def _closure(graph: dict[str, set[str]], start: str) -> set[str]:
    seen, queue = {start}, [start]
    while queue:
        for dep in graph[queue.pop()] - seen:
            seen.add(dep)
            queue.append(dep)
    return seen


def _hash_tree(digest: hashlib._Hash, root: Path, base: Path) -> None:
    for path in sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        digest.update(str(path.relative_to(base)).encode())
        digest.update(path.read_bytes())


def _exports(repo: Path, graph: dict[str, set[str]], exporter: Exporter) -> dict[str, str] | None:
    try:
        return exporter(repo, sorted(graph))
    except ExportError:
        return None


def fingerprint(repo: Path, graph: dict[str, set[str]], package: str, exports: dict[str, str] | None) -> str:
    """Hash of everything `package`'s tests can see: its files, its dependencies' files and resolved sets, the root inputs.

    With no exports (uv cannot answer) the whole lock and root pyproject stand in: any change to them invalidates every package.
    """
    digest = hashlib.sha256()
    for name in sorted(_closure(graph, package)):
        _hash_tree(digest, repo / "packages" / name, repo)
        if exports is not None:
            digest.update(f"{name}:{exports[name]}".encode())
    if exports is None:
        for rel in ("uv.lock", "pyproject.toml"):
            if (repo / rel).is_file():
                digest.update(rel.encode())
                digest.update((repo / rel).read_bytes())
    else:
        digest.update(root_config(repo / "pyproject.toml").encode())
    if (repo / "conftest.py").is_file():
        digest.update(b"conftest.py")
        digest.update((repo / "conftest.py").read_bytes())
    return digest.hexdigest()


def plan(repo: Path, paths: list[str], exporter: Exporter = package_exports) -> list[tuple[str, str]]:
    """`(path, key)` for each of `paths`: a package suite's key is its fingerprint; any other path has none and always runs."""
    graph, _ = workspace(repo)
    exports = _exports(repo, graph, exporter)
    return [(p, fingerprint(repo, graph, p.split("/")[1], exports) if p.startswith("packages/") else "") for p in paths]


def wide_alarm(repo: Path, paths: list[str]) -> str | None:
    """A warning when `paths` hold over half the package suites (`any_gate.too_wide`), else None: a hub, or a rule that fans out."""
    total = len(workspace(repo)[0])
    suites = sum(1 for p in paths if p.startswith("packages/"))
    if too_wide(suites, total):
        return f"this change reaches {suites} of {total} package suites (over half): a hub, a bump or a config change; meant?"
    return None


def _git(repo: Path, *args: str) -> str:
    return capture(["git", *args], cwd=repo, timeout=GIT_TIMEOUT).out


def merge_base(repo: Path) -> str:
    """The upstream merge-base, or HEAD when there is no upstream."""
    return _git(repo, "merge-base", "HEAD", "@{upstream}").strip() or "HEAD"


def changed_files(repo: Path) -> list[str]:
    """Files changed since the upstream merge-base (or HEAD), tracked and untracked."""
    tracked = _git(repo, "diff", "--name-only", merge_base(repo)).splitlines()
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set(tracked) | set(untracked))
