"""What the repo is: detected from its files, overridden by `docs/blueprint/blueprint.toml`."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

from blueprint.model import Profile, walk

if TYPE_CHECKING:
    from pathlib import Path

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


def detect_frameworks(repo: Path) -> tuple[tuple[str, str], ...]:
    """Each framework whose marker file is within three levels of the root, with its folder."""
    found: list[tuple[str, str]] = []
    for name, marker in FRAMEWORK_MARKERS.items():
        found += [(name, str(p.parent.relative_to(repo)) or ".") for p in walk(repo, marker, 4)]
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
