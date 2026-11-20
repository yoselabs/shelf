"""The uv workspace as a graph, and the lock read per package.

A release edits `uv.lock` (45 of 50 commits did) and that must not rerun every suite,
so the lock is read per package: `uv export --package X`
is uv's own answer to "what does X install", and a package is touched when its export differs from the base's. The root `pyproject.toml`
is read the same way: its dependency tables through the exports, its pytest and coverage settings as a change to every suite, the
rest (lint, types, architecture, test paths) as no suite's concern. When uv or the base tree cannot answer, the caller selects everything.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import tarfile
import tempfile
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

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
LOCK_FILES = ("uv.lock", "pyproject.toml")


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


def root_config(manifest: Path) -> str:
    """What of the root pyproject a test run can see, in a stable text form.

    The dependency tables are answered by the exports, and ruff, pyrefly, import-linter, deptry, `tool.uv` and the list of test paths
    are read by whole-repo gate steps, never by a suite. What stays is how pytest and coverage run, which reaches every suite.
    """
    data = tomllib.loads(manifest.read_text()) if manifest.is_file() else {}
    tool: dict[str, Any] = data.get("tool", {})
    options = {k: v for k, v in tool.get("pytest", {}).get("ini_options", {}).items() if k != "testpaths"}
    return json.dumps({"pytest": options, "coverage": tool.get("coverage", {})}, sort_keys=True, default=str)


def extract_base(repo: Path, base: str, dest: Path) -> None:
    listed = subprocess.run(["git", "ls-tree", "-r", "--name-only", base], cwd=repo, capture_output=True, text=True, check=False)
    names = [n for n in listed.stdout.splitlines() if n in LOCK_FILES or re.fullmatch(r"packages/[^/]+/pyproject\.toml", n)]
    if listed.returncode or not names:
        message = f"the base tree {base!r} cannot be read"
        raise ExportError(message)
    archive = subprocess.run(["git", "archive", base, "--", *names], cwd=repo, capture_output=True, check=False)
    if archive.returncode:
        message = f"git archive {base!r} failed"
        raise ExportError(message)
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as bundle:
        bundle.extractall(dest, filter="data")


def touched_between(old: Path, new: Path, exporter: Exporter) -> set[str] | None:
    """The packages whose resolved set differs between two workspace trees; None when a root change outside the dependency tables shows."""
    try:
        if root_config(old / "pyproject.toml") != root_config(new / "pyproject.toml"):
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
            extract_base(repo, base, Path(tmp))
            return touched_between(Path(tmp), repo, exporter)
    except (ExportError, OSError, tarfile.TarError):
        return None
