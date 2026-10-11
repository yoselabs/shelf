"""What the repo is: detected from its files, overridden by `docs/blueprint/blueprint.toml`."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from blueprint.model import SKIP_DIRS, Profile, walk

STATE_DIR = "docs/blueprint"
STATE_FILE = f"{STATE_DIR}/blueprint.toml"
KINDS = ("application", "library", "infrastructure")
OVERRIDE_CODES = ("test-data", "remediated", "not-applicable", "not-supported", "not-detected")


@dataclass(frozen=True)
class Override:
    """A recorded, expiring decision to treat one checkpoint as passing (CONTEXT.md: override)."""

    id: str
    code: str
    reason: str
    expires: date

    def problem(self, today: date) -> str | None:
        """Why this override does not count, or None when it does."""
        if self.code not in OVERRIDE_CODES:
            return f"override code {self.code!r} is not one of {', '.join(OVERRIDE_CODES)}"
        if not self.reason.strip():
            return "override has no reason"
        if self.expires < today:
            return f"override expired {self.expires.isoformat()}"
        return None


@dataclass(frozen=True)
class State:
    """What `blueprint.toml` holds: the profile as declared, overrides, settings per check."""

    declared: dict[str, Any]
    overrides: dict[str, Override]
    settings: dict[str, Any]
    problems: tuple[str, ...]


def load_state(repo: Path) -> State:
    """Read `docs/blueprint/blueprint.toml`; an absent file is an empty state."""
    path = repo / STATE_FILE
    if not path.is_file():
        return State({}, {}, {}, ())
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        return State({}, {}, {}, (f"{STATE_FILE} is not valid TOML: {exc}",))
    problems: list[str] = []
    overrides: dict[str, Override] = {}
    for raw in data.get("override", []):
        expires = raw.get("expires")
        if not isinstance(expires, date):
            problems.append(f"override {raw.get('id')!r} has no expires date")
            continue
        overrides[str(raw.get("id"))] = Override(str(raw.get("id")), str(raw.get("code", "")), str(raw.get("reason", "")), expires)
    return State(data.get("profile", {}), overrides, data.get("settings", {}), tuple(problems))


def detect_stacks(repo: Path) -> tuple[str, ...]:
    """The stacks present, from their manifests."""
    stacks: list[str] = []
    if (repo / "pyproject.toml").is_file():
        stacks.append("python-uv" if (repo / "uv.lock").is_file() else "python")
    if walk(repo, "*.sln", 2) or walk(repo, "*.slnx", 2) or walk(repo, "*.csproj", 3):
        stacks.append("dotnet")
    if (repo / "package.json").is_file():
        stacks.append("node")
    if (repo / "go.mod").is_file():
        stacks.append("go")
    if (repo / "Cargo.toml").is_file():
        stacks.append("rust")
    return tuple(stacks)


# A framework is found by a marker file; its folder is where the marker sits.
FRAMEWORK_MARKERS = {"godot": "project.godot"}


@dataclass(frozen=True)
class DependencyRule:
    """A framework declared as a runtime dependency and confirmed by a use in the project's source."""

    deps: tuple[str, ...]
    used: tuple[str, ...]


# `fastmcp` is also a client library, so the dependency alone would flag a repo that only calls servers; a
# `FastMCP(` in source says this project builds one. The official SDK alone is not matched: the profile prescribes fastmcp.
FRAMEWORK_DEPENDENCIES = {"mcp": DependencyRule(deps=("fastmcp", "fastmcp-slim"), used=("FastMCP(",))}
# Test code builds throwaway servers for any client library, so it is not evidence of a shipped one.
_NOT_SOURCE = SKIP_DIRS | {"tests", "test"}


def _runtime_dependencies(pyproject: Path) -> set[str]:
    """Normalized (PEP 503) names in [project] dependencies and optional-dependencies; dev groups are left out."""
    try:
        project = tomllib.loads(pyproject.read_text()).get("project", {})
    except (tomllib.TOMLDecodeError, OSError):
        return set()
    specs = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        specs += extra
    names = (re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", str(spec).strip()) for spec in specs)
    return {re.sub(r"[-_.]+", "-", m.group().lower()) for m in names if m}


def _source_uses(folder: Path, needles: tuple[str, ...]) -> bool:
    for here, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in _NOT_SOURCE]
        for name in files:
            if name.endswith(".py") and any(n in (Path(here) / name).read_text(errors="replace") for n in needles):
                return True
    return False


def detect_frameworks(repo: Path) -> tuple[tuple[str, str], ...]:
    """Each framework found within three levels of the root, with its folder: by marker file, then by dependency."""
    found: list[tuple[str, str]] = []
    for name, marker in FRAMEWORK_MARKERS.items():
        found += [(name, str(p.parent.relative_to(repo)) or ".") for p in walk(repo, marker, 4)]
    for name, rule in FRAMEWORK_DEPENDENCIES.items():
        for pyproject in walk(repo, "pyproject.toml", 4):
            if _runtime_dependencies(pyproject) & set(rule.deps) and _source_uses(pyproject.parent, rule.used):
                found.append((name, str(pyproject.parent.relative_to(repo)) or "."))
    return tuple(found)


def _detect_kind(repo: Path) -> str:
    pyproject = repo / "pyproject.toml"
    if pyproject.is_file():
        data = tomllib.loads(pyproject.read_text())
        if "workspace" in data.get("tool", {}).get("uv", {}) and not data.get("project", {}).get("scripts"):
            return "library"
    if walk(repo, "*.tf", 2) or (repo / "ansible.cfg").is_file():
        return "infrastructure"
    return "application"


def detect(repo: Path, state: State) -> Profile:
    """The profile: what the state declares, else what the files say."""
    declared = state.declared
    return Profile(
        kind=str(declared.get("kind") or _detect_kind(repo)),
        surfaces=tuple(declared.get("surfaces", ())),
        traits=tuple(declared.get("traits", ())),
        stacks=tuple(declared.get("stacks", ())) or detect_stacks(repo),
        tracker="beads" if (repo / ".beads").is_dir() else declared.get("tracker"),
        frameworks=tuple((str(f), str(r)) for f, r in declared.get("frameworks", {}).items()) or detect_frameworks(repo),
    )
