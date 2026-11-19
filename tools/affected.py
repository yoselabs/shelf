#!/usr/bin/env python3
"""Which test directories a change touches: the shelf's affected-only test run (Nx-style).

Prints pytest paths, one per line: the fitness tests (`tests`, without its onboarding tests unless an onboarding
input changed), plus `packages/<p>/tests`
for every package the change touches and every package that depends on one of them, walked
through the uv-workspace graph (each member's dependencies, optional dependencies and
dependency groups). A change anywhere the graph cannot see — `conftest.py`, the `justfile`, CI, an
unknown path, or a pytest plugin package that loads into every run — selects every package.

The lock is read per package, not as one file (ADR 0021): a release edits `uv.lock` (45 of the last 50
commits did), and that must not rerun every suite. `uv export --package X` is uv's own answer to "what does X
install"; a package is touched when its export differs from the base's. The root `pyproject.toml` is read the
same way: its dependency tables through the exports, its pytest and coverage settings as a change to every suite, the
rest (lint, types, architecture, test paths) as no suite's concern. When uv or the base tree cannot answer, every package
is selected: never a silent pass.

The change is the diff from the upstream merge-base (HEAD when there is no upstream) to the
working tree, plus untracked files. `just check-all` runs everything regardless.

`--plan` prints `path<TAB>key` per suite for `any-gate test`: a package suite's key is its fingerprint (its files, its dependencies' files
and resolved sets, the root inputs every test run reads), and `any-gate`'s receipts skip a suite whose key already passed. Fitness tests
carry no key and always run: they read the whole repo.
Stdlib only, so it runs as bare `python3`.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Paths whose change no package test can observe: docs, the ontology, agent files. The fitness
# tests in `tests/` (always run) cover what of these is checked at all.
_NO_PACKAGE_EFFECT = (
    "tests/",
    "tools/",
    "docs/",
    "catalog/",
    "use-cases/",
    "ledger/",
    "skills/",
    "evals/",
    ".beads/",
    ".agents/",
    ".claude/",
    ".claude-plugin/",
)
_NO_PACKAGE_EFFECT_FILES = frozenset({".gitignore", "LICENSE", "README.md", "AGENTS.md", "CLAUDE.md"})
# The fitness tests that build real consumer repos (8-14 s each, 2026-10-11) read only the onboarding machinery, so
# they run when an input of it changes; every other fitness test runs on every change, and `check-all` runs them all.
_ONBOARDING_TESTS = ("test_onboard_", "test_bootstrap_target.py")
_ONBOARDING_INPUTS = ("tools/onboard/", "tools/preset_drift.py", ".agents/skills/onboard-consumer/", "tests/conftest.py")
_ONBOARDING_INPUT_FILES = frozenset(
    {"justfile", "pyproject.toml", "uv.lock", "conftest.py", ".pre-commit-config.yaml", ".beads/config.yaml"}
)
# What one onboarding test reads beyond those: the blueprint concern or recipe it checks its result with.
_ONBOARDING_EXTRA = {
    "test_onboard_beads.py": ("packages/blueprint/src/blueprint/concerns/backlog.py",),
    "test_onboard_hooks.py": ("packages/blueprint/src/blueprint/recipes/",),
}
_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirements(project: dict[str, Any], groups: dict[str, list[Any]]) -> set[str]:
    reqs: list[Any] = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        reqs += extra
    for group in groups.values():
        reqs += group
    return {_norm(m.group(1)) for r in reqs if isinstance(r, str) and (m := _REQ_NAME.match(r))}


def workspace(repo: Path) -> tuple[dict[str, set[str]], set[str]]:
    """`(dir -> dirs it depends on, dirs that are pytest plugins)` for every `packages/*` member."""
    names: dict[str, str] = {}
    raw: dict[str, set[str]] = {}
    plugins: set[str] = set()
    for manifest in sorted(repo.glob("packages/*/pyproject.toml")):
        data = tomllib.loads(manifest.read_text())
        project = data.get("project", {})
        directory = manifest.parent.name
        names[_norm(project.get("name", directory))] = directory
        raw[directory] = _requirements(project, data.get("dependency-groups", {}))
        if "pytest11" in project.get("entry-points", {}):
            plugins.add(directory)
    graph = {d: {names[r] for r in reqs if r in names and names[r] != d} for d, reqs in raw.items()}
    return graph, plugins


class ExportError(Exception):
    """`uv export`, or the base tree it needs, could not answer."""


# (a workspace directory, package directories) -> each package's export hash
Exporter = Callable[[Path, list[str]], dict[str, str]]
_LOCK_FILES = ("uv.lock", "pyproject.toml")


def member_names(repo: Path) -> dict[str, str]:
    """`packages/*` directory -> its project name, which `uv export --package` takes."""
    names: dict[str, str] = {}
    for manifest in sorted(repo.glob("packages/*/pyproject.toml")):
        names[manifest.parent.name] = tomllib.loads(manifest.read_text()).get("project", {}).get("name", manifest.parent.name)
    return names


def package_exports(repo: Path, packages: list[str]) -> dict[str, str]:
    """Hash of `uv export` per package: the third-party set its tests install (runtime and dev group), not the workspace's code."""
    names = member_names(repo)
    hashes: dict[str, str] = {}
    for directory in packages:
        cmd = ["uv", "export", "--frozen", "--package", names[directory], "--group", "dev"]
        cmd += ["--no-emit-workspace", "--no-hashes", "--no-header", "--no-annotate", "-q"]
        done = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, check=False)
        if done.returncode:
            message = f"uv export --package {names[directory]} failed: {done.stderr.strip()[:200]}"
            raise ExportError(message)
        hashes[directory] = hashlib.sha256(done.stdout.encode()).hexdigest()
    return hashes


def _root_config(manifest: Path) -> str:
    """What of the root pyproject a test run can see, in a stable text form.

    The dependency tables are answered by the exports, and ruff, pyrefly, import-linter, deptry, `tool.uv` and the list of test paths
    are read by whole-repo gate steps, never by a suite. What stays is how pytest and coverage run, which reaches every suite.
    """
    data = tomllib.loads(manifest.read_text()) if manifest.is_file() else {}
    tool: dict[str, Any] = data.get("tool", {})
    options = {k: v for k, v in tool.get("pytest", {}).get("ini_options", {}).items() if k != "testpaths"}
    return json.dumps({"pytest": options, "coverage": tool.get("coverage", {})}, sort_keys=True, default=str)


def _extract_base(repo: Path, base: str, dest: Path) -> None:
    listed = subprocess.run(["git", "ls-tree", "-r", "--name-only", base], cwd=repo, capture_output=True, text=True, check=False)
    names = [n for n in listed.stdout.splitlines() if n in _LOCK_FILES or re.fullmatch(r"packages/[^/]+/pyproject\.toml", n)]
    if listed.returncode or not names:
        message = f"the base tree {base!r} cannot be read"
        raise ExportError(message)
    archive = subprocess.run(["git", "archive", base, "--", *names], cwd=repo, capture_output=True, check=False)
    if archive.returncode:
        message = f"git archive {base!r} failed"
        raise ExportError(message)
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as bundle:
        bundle.extractall(dest, filter="data")


def _touched_between(old: Path, new: Path, exporter: Exporter) -> set[str] | None:
    """The packages whose resolved set differs between two workspace trees; None when a root change outside the dependency tables shows."""
    try:
        if _root_config(old / "pyproject.toml") != _root_config(new / "pyproject.toml"):
            return None
        before = exporter(old, sorted(workspace(old)[0]))
        after = exporter(new, sorted(workspace(new)[0]))
    except (ExportError, OSError, tomllib.TOMLDecodeError):
        return None
    return {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}


def lock_touched(repo: Path, base: str, exporter: Exporter = package_exports) -> set[str] | None:
    """The packages whose resolved set differs from `base`'s, or None when that cannot be told (the caller selects everything)."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _extract_base(repo, base, Path(tmp))
            return _touched_between(Path(tmp), repo, exporter)
    except (ExportError, OSError, tarfile.TarError):
        return None


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
                _extract_base(repo, f"{sha}^", Path(old))
                _extract_base(repo, sha, Path(new))
            except ExportError:
                continue
            reached = affected_packages(Path(new), changed, lambda: _touched_between(Path(old), Path(new), exporter))
        rows.append((sha, len(changed), len(reached)))
    return rows


def _fitness(repo: Path, changed: list[str]) -> list[str]:
    """`tests` whole when an onboarding input changed; else each fitness test file but the onboarding ones a change misses."""
    if any(p.startswith(_ONBOARDING_INPUTS) or p in _ONBOARDING_INPUT_FILES for p in changed):
        return ["tests"]

    def runs(name: str) -> bool:
        reads = (f"tests/{name}", *_ONBOARDING_EXTRA.get(name, ()))
        return not name.startswith(_ONBOARDING_TESTS) or any(p.startswith(reads) for p in changed)

    files = [p.relative_to(repo).as_posix() for p in sorted((repo / "tests").glob("test_*.py")) if runs(p.name)]
    return files or ["tests"]


def affected_packages(repo: Path, changed: list[str], lock: Callable[[], set[str] | None] | None = None) -> set[str]:
    """The package directories `changed` reaches: the changed ones and, through the graph, everything depending on them.

    `lock` answers which packages the lock files changed for (see `lock_touched`); without it a lock change selects everything.
    """
    graph, plugins = workspace(repo)
    every = sorted(graph)
    touched: set[str] = set()
    from_lock: set[str] | None = None
    asked = False
    for path in changed:
        parts = path.split("/")
        if parts[0] == "packages" and len(parts) > 2 and parts[1] in graph:
            touched.add(parts[1])
        elif path.startswith(_NO_PACKAGE_EFFECT) or path in _NO_PACKAGE_EFFECT_FILES:
            continue
        elif path in _LOCK_FILES and lock is not None:
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


def affected(repo: Path, changed: list[str], lock: Callable[[], set[str] | None] | None = None) -> list[str]:
    """The pytest paths to run for `changed` (repo-relative paths)."""
    seen = affected_packages(repo, changed, lock)
    return [*_fitness(repo, changed), *(f"packages/{d}/tests" for d in sorted(seen) if (repo / "packages" / d / "tests").is_dir())]


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
        digest.update(_root_config(repo / "pyproject.toml").encode())
    if (repo / "conftest.py").is_file():
        digest.update(b"conftest.py")
        digest.update((repo / "conftest.py").read_bytes())
    return digest.hexdigest()


def plan(repo: Path, paths: list[str], exporter: Exporter = package_exports) -> list[tuple[str, str]]:
    """`(path, key)` for each of `paths`: a package suite's key is its fingerprint; any other path has none and always runs."""
    graph, _ = workspace(repo)
    exports = _exports(repo, graph, exporter)
    return [(p, fingerprint(repo, graph, p.split("/")[1], exports) if p.startswith("packages/") else "") for p in paths]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False).stdout


def merge_base(repo: Path) -> str:
    """The upstream merge-base, or HEAD when there is no upstream."""
    return _git(repo, "merge-base", "HEAD", "@{upstream}").strip() or "HEAD"


def changed_files(repo: Path) -> list[str]:
    """Files changed since the upstream merge-base (or HEAD), tracked and untracked."""
    base = merge_base(repo)
    tracked = _git(repo, "diff", "--name-only", base).splitlines()
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set(tracked) | set(untracked))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=".", help="the repo (default: cwd)")
    parser.add_argument("--explain", action="store_true", help="also print the changed files to stderr")
    parser.add_argument("--plan", action="store_true", help="print `path<TAB>key` per suite (the input of `any-gate test`)")
    parser.add_argument(
        "--reach", type=int, metavar="N", help="print how many package suites each of the last N commits reaches, then exit"
    )
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    if args.reach:
        rows = reach(repo, args.reach)
        for sha, files, suites in rows:
            print(f"{sha} files={files} suites={suites}")
        sizes = sorted(suites for _, _, suites in rows)
        total = len(workspace(repo)[0])
        print(f"commits={len(rows)} median={sizes[len(sizes) // 2] if sizes else 0} max={sizes[-1] if sizes else 0} of {total} packages")
        return 0
    changed = changed_files(repo)
    paths = affected(repo, changed, lambda: lock_touched(repo, merge_base(repo)))
    if args.explain:
        print(f"affected: {len(changed)} changed file(s): {' '.join(changed) or '-'}", file=sys.stderr)
    print("\n".join(f"{path}\t{key}" for path, key in plan(repo, paths)) if args.plan else "\n".join(paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
