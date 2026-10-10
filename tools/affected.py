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
Stdlib only, so it runs as bare `python3`.
"""

from __future__ import annotations

import argparse
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
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    changed = changed_files(repo)
    if args.explain:
        print(f"affected: {len(changed)} changed file(s): {' '.join(changed) or '-'}", file=sys.stderr)
    print("\n".join(affected(repo, changed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
