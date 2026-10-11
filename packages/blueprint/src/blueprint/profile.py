"""What the repo is: detected from its files, overridden by `docs/blueprint/blueprint.toml`."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from blueprint import adr
from blueprint.model import SKIP_DIRS, Profile, dockerfiles, walk

STATE_DIR = "docs/blueprint"
STATE_FILE = f"{STATE_DIR}/blueprint.toml"
KINDS = ("application", "library", "infrastructure")
OVERRIDE_CODES = ("test-data", "remediated", "not-applicable", "not-supported", "not-detected")


_ADR_NUMBER = re.compile(r"^\d{4}$")


def _adr_problem(repo: Path, number: str) -> str | None:
    """Why the ADR a justification cites does not count: not a number, absent from docs/adr/, or not accepted."""
    if not _ADR_NUMBER.match(number):
        return f"adr {number!r} is not an NNNN number"
    path = next(iter(sorted((repo / adr.FOLDER).glob(f"{number}-*.md"))), None)
    if path is None:
        return f"ADR {number} is not in {adr.FOLDER}/"
    found = adr.parse(path)
    status = found.fields.get("status") if found else None
    return None if status == "accepted" else f"ADR {number} is not accepted (status: {status or 'unreadable'})"


def justification_problem(what: str, reason: str, expires: date | None, adr_number: str, repo: Path) -> str | None:
    """Why an exception to a blueprint rule is not justified, or None.

    One rule for every exception (an override, an ignored path): a reason, and either an `expires` date
    (a temporary exception) or an `adr` naming an accepted ADR that records the durable decision.
    """
    if not reason.strip():
        return f"{what} has no reason"
    if expires is None and not adr_number:
        return f"{what} needs an expires date, or an adr naming the accepted ADR that records the decision"
    if adr_number and (found := _adr_problem(repo, adr_number)):
        return f"{what}: {found}"
    return None


def _date_or_none(raw: object) -> date | None:
    return raw if isinstance(raw, date) else None


@dataclass(frozen=True)
class Override:
    """A recorded, justified decision to treat one checkpoint as passing (CONTEXT.md: override)."""

    id: str
    code: str
    reason: str
    # An override lasts until `expires`, or without end when `adr` names the accepted ADR that decided it.
    expires: date | None = None
    adr: str = ""
    # Set at load when the justification itself is wrong (no reason, no expiry or ADR, a missing ADR).
    unjustified: str | None = None

    def problem(self, today: date) -> str | None:
        """Why this override does not count, or None when it does."""
        if self.code not in OVERRIDE_CODES:
            return f"override code {self.code!r} is not one of {', '.join(OVERRIDE_CODES)}"
        if self.unjustified:
            return self.unjustified
        if self.expires is not None and self.expires < today:
            return f"override expired {self.expires.isoformat()}"
        return None

    @property
    def lasts(self) -> str:
        """How long it holds, for a report: `until <date>` or `by ADR NNNN`."""
        return f"until {self.expires.isoformat()}" if self.expires is not None else f"by ADR {self.adr}"


@dataclass(frozen=True)
class Ignore:
    """A path the repo declared throwaway or vendored, so detection and role globs skip it. Justified like an override."""

    path: str
    reason: str
    expires: date | None = None
    adr: str = ""
    problem: str | None = None


@dataclass(frozen=True)
class State:
    """What `blueprint.toml` holds: the profile as declared, overrides, settings per check."""

    declared: dict[str, Any]
    overrides: dict[str, Override]
    settings: dict[str, Any]
    problems: tuple[str, ...]
    ignores: tuple[Ignore, ...] = ()


def _load_overrides(raw_list: list[dict[str, Any]], repo: Path, problems: list[str]) -> dict[str, Override]:
    overrides: dict[str, Override] = {}
    for raw in raw_list:
        oid = str(raw.get("id", ""))
        if not oid:
            problems.append("an override has no id")
            continue
        expires = _date_or_none(raw.get("expires"))
        adr_number = str(raw.get("adr", ""))
        unjustified = justification_problem(f"override {oid!r}", str(raw.get("reason", "")), expires, adr_number, repo)
        if unjustified:
            problems.append(unjustified)
        overrides[oid] = Override(oid, str(raw.get("code", "")), str(raw.get("reason", "")), expires, adr_number, unjustified)
    return overrides


def _load_ignores(raw_list: list[dict[str, Any]], repo: Path, today: date, problems: list[str]) -> tuple[Ignore, ...]:
    ignores: list[Ignore] = []
    for raw in raw_list:
        path = str(raw.get("path", "")).strip()
        expires = _date_or_none(raw.get("expires"))
        adr_number = str(raw.get("adr", ""))
        why = str(raw.get("reason", ""))
        problem = (
            f"ignore entry has no path (reason: {why!r})"
            if not path
            else justification_problem(f"ignore {path!r}", why, expires, adr_number, repo)
        )
        if problem is None and expires is not None and expires < today:
            problem = f"ignore {path!r} expired {expires.isoformat()}"
        if problem:
            problems.append(problem)
        ignores.append(Ignore(path, why, expires, adr_number, problem))
    return tuple(ignores)


def load_state(repo: Path, today: date | None = None) -> State:
    """Read `docs/blueprint/blueprint.toml`; an absent file is an empty state."""
    path = repo / STATE_FILE
    if not path.is_file():
        return State({}, {}, {}, ())
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        return State({}, {}, {}, (f"{STATE_FILE} is not valid TOML: {exc}",))
    problems: list[str] = []
    overrides = _load_overrides(data.get("override", []), repo, problems)
    declared = data.get("profile", {})
    ignores = _load_ignores(declared.get("ignore", []), repo, today or date.today(), problems)  # noqa: DTZ011 -- a calendar date in the owner's zone
    return State(declared, overrides, data.get("settings", {}), tuple(problems), ignores)


# Compose files by name; a repo with many (one per service folder) still gets one `compose` table.
COMPOSE_FILES = ("compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml")


# A shell stack is two or more scripts, or one long enough to hold logic; a lone `exec` wrapper is not one.
# bd writes its own hook shims under .beads/hooks.
_SHELL_MIN_LINES = 10


# A few scripts beside a repo's real language are helpers (a2kay: one macOS packaging script): they get shellcheck and
# strict mode, not a formatter, hooks and a conventions file of their own.
_SHELL_PRIMARY_SCRIPTS = 5
_CODE_STACKS = ("python-uv", "python", "dotnet", "node", "go", "rust")


def _secondary(found: dict[str, list[str]], scripts: list[str]) -> bool:
    return len(scripts) < _SHELL_PRIMARY_SCRIPTS and any(s in found for s in _CODE_STACKS)


def _shell_scripts(repo: Path, skip: tuple[str, ...]) -> list[str]:
    found = walk(repo, "*.sh", 3, (*skip, ".beads/hooks"))
    if len(found) == 1 and len(found[0].read_text(errors="replace").splitlines()) < _SHELL_MIN_LINES:
        return []
    return [p.relative_to(repo).as_posix() for p in found]


def _stack_files(repo: Path, skip: tuple[str, ...]) -> dict[str, list[str]]:
    """Each stack present with the files that set it, from their manifests."""
    found: dict[str, list[str]] = {}
    if (repo / "pyproject.toml").is_file():
        locked = (repo / "uv.lock").is_file()
        found["python-uv" if locked else "python"] = ["pyproject.toml", *(["uv.lock"] if locked else [])]
    dotnet = [*walk(repo, "*.sln", 2, skip), *walk(repo, "*.slnx", 2, skip), *walk(repo, "*.csproj", 3, skip)]
    if dotnet:
        found["dotnet"] = [p.relative_to(repo).as_posix() for p in dotnet]
    if flakes := walk(repo, "flake.nix", 3, skip):
        found["nix"] = [p.relative_to(repo).as_posix() for p in flakes]
    if composes := [p for pattern in COMPOSE_FILES for p in walk(repo, pattern, 3, skip)]:
        found["compose"] = sorted(p.relative_to(repo).as_posix() for p in composes)
    if images := dockerfiles(repo, skip):
        found["dockerfile"] = [p.relative_to(repo).as_posix() for p in images]
    for stack, manifest in (("node", "package.json"), ("go", "go.mod"), ("rust", "Cargo.toml")):
        if (repo / manifest).is_file():
            found[stack] = [manifest]
    if scripts := _shell_scripts(repo, skip):
        found["shell-scripts" if _secondary(found, scripts) else "shell"] = scripts
    return found


def detect_stacks(repo: Path, skip: tuple[str, ...] = ()) -> tuple[str, ...]:
    """The stacks present, from their manifests."""
    return tuple(_stack_files(repo, skip))


def _evidence_files(files: list[str]) -> str:
    return ", ".join(files[:3]) + (f" and {len(files) - 3} more" if len(files) > 3 else "")


@dataclass(frozen=True)
class Marker:
    """The file that marks a framework project; `folder`, when set, is the folder it must sit in."""

    file: str
    folder: str = ""

    def root(self, found: Path) -> Path | None:
        """The project folder for a matching file: where it sits, or the parent of its `folder`; None when it is elsewhere."""
        if not self.folder:
            return found.parent
        return found.parent.parent if found.parent.name == self.folder else None


# Godot's marker sits in the project folder, Unity's one folder down (ProjectSettings/).
FRAMEWORK_MARKERS = {"godot": Marker("project.godot"), "unity": Marker("ProjectVersion.txt", "ProjectSettings")}


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


def detect_frameworks(repo: Path, skip: tuple[str, ...] = ()) -> tuple[tuple[str, str], ...]:
    """Each framework found within three levels of the root, with its folder: by marker file, then by dependency."""
    found: list[tuple[str, str]] = []
    for name, marker in FRAMEWORK_MARKERS.items():
        roots = (marker.root(p) for p in walk(repo, marker.file, 5 if marker.folder else 4, skip))
        found += [(name, str(r.relative_to(repo)) or ".") for r in roots if r is not None]
    for name, rule in FRAMEWORK_DEPENDENCIES.items():
        for pyproject in walk(repo, "pyproject.toml", 4, skip):
            if _runtime_dependencies(pyproject) & set(rule.deps) and _source_uses(pyproject.parent, rule.used):
                found.append((name, str(pyproject.parent.relative_to(repo)) or "."))
    return tuple(found)


def _detect_kind(repo: Path, skip: tuple[str, ...] = ()) -> str:
    pyproject = repo / "pyproject.toml"
    if pyproject.is_file():
        data = tomllib.loads(pyproject.read_text())
        if "workspace" in data.get("tool", {}).get("uv", {}) and not data.get("project", {}).get("scripts"):
            return "library"
    if walk(repo, "*.tf", 2, skip) or (repo / "ansible.cfg").is_file():
        return "infrastructure"
    return "application"


def detect(repo: Path, state: State) -> Profile:
    """The profile: what the state declares, else what the files say."""
    declared = state.declared
    skip = tuple(i.path for i in state.ignores if i.problem is None)
    declared_stacks = tuple(declared.get("stacks", ()))
    found: dict[str, list[str]] = {} if declared_stacks else _stack_files(repo, skip)
    stack_files = (
        tuple((s, f"declared in {STATE_FILE}") for s in declared_stacks)
        if declared_stacks
        else tuple((s, _evidence_files(files)) for s, files in found.items())
    )
    return Profile(
        kind=str(declared.get("kind") or _detect_kind(repo, skip)),
        surfaces=tuple(declared.get("surfaces", ())),
        traits=tuple(declared.get("traits", ())),
        stacks=declared_stacks or tuple(found),
        tracker="beads" if (repo / ".beads").is_dir() else declared.get("tracker"),
        frameworks=tuple((str(f), str(r)) for f, r in declared.get("frameworks", {}).items()) or detect_frameworks(repo, skip),
        stack_files=stack_files,
        ignore=skip,
    )
