#!/usr/bin/env python3
"""Which test directories a change touches: the shelf's affected-only test run (Nx-style).

Prints pytest paths, one per line: always `tests` (the fitness tests), plus `packages/<p>/tests`
for every package the change touches and every package that depends on one of them, walked
through the uv-workspace graph (each member's dependencies, optional dependencies and
dependency groups). A change anywhere the graph cannot see — the root `pyproject.toml`,
`uv.lock`, `conftest.py`, the `Makefile`, CI, an unknown path, or a pytest plugin package that
loads into every run — selects every package.

The change is the diff from the upstream merge-base (HEAD when there is no upstream) to the
working tree, plus untracked files. `make check-all` runs everything regardless.

Result cache (`--skip-passed`, `--record`): a package's fingerprint hashes its files, the files of
every package it depends on, and the root files every test run reads (uv.lock, pyproject.toml,
conftest.py). After a green run `--record` stores the fingerprints; `--skip-passed` then drops each
package whose current fingerprint is stored, so an unchanged package never re-runs. `tests/` is never
cached: the fitness tests read the whole repo.
Stdlib only, so it runs as bare `python3`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

# Paths whose change no package test can observe: docs, the ontology, agent files. The fitness
# tests in `tests/` (always run) cover what of these is checked at all.
_NO_PACKAGE_EFFECT = (
    "tests/",
    "tools/",
    "docs/",
    "openspec/",
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


def affected(repo: Path, changed: list[str]) -> list[str]:
    """The pytest paths to run for `changed` (repo-relative paths)."""
    graph, plugins = workspace(repo)
    every = sorted(graph)
    touched: set[str] = set()
    for path in changed:
        parts = path.split("/")
        if parts[0] == "packages" and len(parts) > 2 and parts[1] in graph:
            touched.add(parts[1])
        elif path.startswith(_NO_PACKAGE_EFFECT) or path in _NO_PACKAGE_EFFECT_FILES:
            continue
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

    return ["tests", *(f"packages/{d}/tests" for d in sorted(seen) if (repo / "packages" / d / "tests").is_dir())]


CACHE = Path(".cache/affected-passed.json")
_ROOT_INPUTS = ("uv.lock", "pyproject.toml", "conftest.py")
_KEEP = 20  # fingerprints remembered per package


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


def fingerprint(repo: Path, graph: dict[str, set[str]], package: str) -> str:
    """Hash of everything `package`'s tests can see: its files, its dependencies' files, the root inputs."""
    digest = hashlib.sha256()
    for name in sorted(_closure(graph, package)):
        _hash_tree(digest, repo / "packages" / name, repo)
    for rel in _ROOT_INPUTS:
        if (repo / rel).is_file():
            digest.update(rel.encode())
            digest.update((repo / rel).read_bytes())
    return digest.hexdigest()


def _load_cache(repo: Path) -> dict[str, list[str]]:
    try:
        data = json.loads((repo / CACHE).read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def skip_passed(repo: Path, paths: list[str]) -> list[str]:
    """`paths` without the package suites whose current fingerprint already passed."""
    graph, _ = workspace(repo)
    cache = _load_cache(repo)
    return [p for p in paths if p == "tests" or fingerprint(repo, graph, p.split("/")[1]) not in cache.get(p.split("/")[1], [])]


def record(repo: Path, paths: list[str]) -> None:
    """Store the current fingerprint of every package suite in `paths` as passed."""
    graph, _ = workspace(repo)
    cache = _load_cache(repo)
    for p in paths:
        if p.startswith("packages/"):
            name = p.split("/")[1]
            cache[name] = [fingerprint(repo, graph, name), *[f for f in cache.get(name, []) if f != fingerprint(repo, graph, name)]][:_KEEP]
    (repo / CACHE).parent.mkdir(parents=True, exist_ok=True)
    (repo / CACHE).write_text(json.dumps(cache, indent=1, sort_keys=True))


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False).stdout


def changed_files(repo: Path) -> list[str]:
    """Files changed since the upstream merge-base (or HEAD), tracked and untracked."""
    base = _git(repo, "merge-base", "HEAD", "@{upstream}").strip() or "HEAD"
    tracked = _git(repo, "diff", "--name-only", base).splitlines()
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set(tracked) | set(untracked))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=".", help="the repo (default: cwd)")
    parser.add_argument("--explain", action="store_true", help="also print the changed files to stderr")
    parser.add_argument("--skip-passed", action="store_true", help="drop package suites whose fingerprint already passed")
    parser.add_argument("--record", nargs="*", metavar="PATH", help="store these suites' fingerprints as passed, then exit")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    if args.record is not None:
        record(repo, args.record)
        return 0
    changed = changed_files(repo)
    paths = affected(repo, changed)
    if args.skip_passed:
        kept = skip_passed(repo, paths)
        if args.explain:
            print(f"affected: {len(paths) - len(kept)} suite(s) skipped, unchanged since they passed", file=sys.stderr)
        paths = kept
    if args.explain:
        print(f"affected: {len(changed)} changed file(s): {' '.join(changed) or '-'}", file=sys.stderr)
    print("\n".join(paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
