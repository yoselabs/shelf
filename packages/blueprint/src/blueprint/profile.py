"""What the repo is: detected from its files, overridden by `docs/blueprint/blueprint.toml`."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from blueprint import adr
from blueprint.facts import KINDS, SURFACES, TRAITS, Judgement, detect_facts, judgement_problem
from blueprint.model import SKIP_DIRS, Context, Profile, dockerfiles, is_skipped, override_toml, walk

STATE_DIR = "docs/blueprint"
STATE_FILE = f"{STATE_DIR}/blueprint.toml"
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


DECIDERS = ("owner", "agent")
# The id an override uses to skip a path in detection and role globs (it replaces `[[profile.ignore]]`).
DETECTION = "detection"
_LINE_SCOPE = re.compile(r"^(?P<path>.+):(?P<line>\d+)$")


@dataclass(frozen=True)
class Override:
    """A recorded, justified decision to treat one checkpoint as passing, everywhere or for a scope (CONTEXT.md: override).

    `scope` narrows it: a path glob, `<path>:<line>`, or `service:<compose service>`. Without a scope it overrides the
    whole row; with one, the check still runs and drops the offenders the scope names (`Context.excused`).
    """

    id: str
    reason: str
    scope: str = ""
    # Legacy and optional: one of OVERRIDE_CODES, when given.
    code: str = ""
    decided_by: str = "agent"
    # An override lasts until `expires`, or without end when `adr` names the accepted ADR that decided it.
    expires: date | None = None
    adr: str = ""
    # Set at load when the justification itself is wrong (no reason, no expiry or ADR, a missing ADR).
    unjustified: str | None = None

    def problem(self, today: date) -> str | None:
        """Why this override does not count, or None when it does."""
        if self.code and self.code not in OVERRIDE_CODES:
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

    def covers(self, path: str | None, line: int | None, service: str | None) -> bool:
        """Whether a scoped override names this offender: a service, a path (glob or folder), or a path and line."""
        if not self.scope:
            return False
        if self.scope.startswith("service:"):
            return service is not None and self.scope.removeprefix("service:") == service
        if path is None:
            return False
        if (m := _LINE_SCOPE.match(self.scope)) is not None:
            return line is not None and line == int(m.group("line")) and is_skipped(path, (m.group("path"),))
        return is_skipped(path, (self.scope,))

    def as_dict(self) -> dict[str, object]:
        """For the JSON report."""
        return {
            "id": self.id,
            "scope": self.scope,
            "reason": self.reason,
            "decided_by": self.decided_by,
            "expires": self.expires.isoformat() if self.expires is not None else None,
            "adr": self.adr,
            "problem": self.unjustified,
        }


@dataclass(frozen=True)
class State:
    """What `blueprint.toml` holds: the profile as declared, overrides, settings per check."""

    declared: dict[str, Any]
    overrides: tuple[Override, ...]
    settings: dict[str, Any]
    problems: tuple[str, ...]
    # Paths detection and role globs skip: the justified `detection` overrides and the old `[[profile.ignore]]` entries.
    skip: tuple[str, ...] = ()
    # Not failures: an old shape still read, with the exact text to replace it.
    notices: tuple[str, ...] = ()
    # The justified classification: `[[profile.classified]]` and `[[profile.rejected]]`, the refused ones left out.
    classified: tuple[Judgement, ...] = ()
    rejected: tuple[Judgement, ...] = ()


def _load_judgements(declared: dict[str, Any], problems: list[str]) -> tuple[tuple[Judgement, ...], tuple[Judgement, ...]]:
    loaded: dict[str, list[Judgement]] = {"classified": [], "rejected": []}
    for kind, found in loaded.items():
        for raw in declared.get(kind, []):
            judgement, problem = judgement_problem(kind, raw)
            if problem:
                problems.append(problem)
            elif judgement is not None:
                found.append(judgement)
    return tuple(loaded["classified"]), tuple(loaded["rejected"])


def _load_override(raw: dict[str, Any], repo: Path, problems: list[str]) -> Override | None:
    oid = str(raw.get("id", ""))
    if not oid:
        problems.append("an override has no id")
        return None
    scope = str(raw.get("scope", "")).strip()
    reason = str(raw.get("reason", ""))
    expires = _date_or_none(raw.get("expires"))
    adr_number = str(raw.get("adr", ""))
    decided_by = str(raw.get("decided_by", "agent"))
    what = f"override {oid!r}" + (f" ({scope})" if scope else "")
    unjustified = justification_problem(what, reason, expires, adr_number, repo)
    if unjustified is None and decided_by not in DECIDERS:
        unjustified = f"{what}: decided_by {decided_by!r} is not one of {', '.join(DECIDERS)}"
    if unjustified is None and oid == DETECTION and not scope:
        unjustified = f"{what} needs a scope: the path glob detection skips"
    if unjustified:
        problems.append(unjustified)
    return Override(oid, reason, scope, str(raw.get("code", "")), decided_by, expires, adr_number, unjustified)


def _legacy_ignore(raw: dict[str, Any], repo: Path, today: date, problems: list[str]) -> tuple[Override | None, str]:
    """An old `[[profile.ignore]]` entry as the detection override it becomes, and the notice to move it."""
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
    if not path:
        return None, ""
    replacement = override_toml(DETECTION, path, why, expires=expires, adr_number=adr_number)
    notice = (
        f"[[profile.ignore]] path = {path!r} still works but is the old shape: move it to an [[override]] in "
        f"{STATE_FILE}, then delete the ignore:\n{replacement}"
    )
    return Override(DETECTION, why, path, "", "agent", expires, adr_number, problem), notice


def load_state(repo: Path, today: date | None = None) -> State:
    """Read `docs/blueprint/blueprint.toml`; an absent file is an empty state."""
    path = repo / STATE_FILE
    if not path.is_file():
        return State({}, (), {}, ())
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        return State({}, (), {}, (f"{STATE_FILE} is not valid TOML: {exc}",))
    today = today or date.today()  # noqa: DTZ011 -- a calendar date in the owner's zone
    problems: list[str] = []
    overrides = [o for raw in data.get("override", []) if (o := _load_override(raw, repo, problems)) is not None]
    declared = data.get("profile", {})
    notices: list[str] = []
    for raw in declared.get("ignore", []):
        legacy, notice = _legacy_ignore(raw, repo, today, problems)
        if legacy is not None:
            overrides.append(legacy)
            notices.append(notice)
    skip = tuple(o.scope for o in overrides if o.id == DETECTION and o.scope and o.problem(today) is None)
    problems += [
        f"detection override {o.scope!r}: {o.problem(today)}"
        for o in overrides
        if o.id == DETECTION and o.scope and o.unjustified is None and o.problem(today)
    ]
    classified, rejected = _load_judgements(declared, problems)
    return State(declared, tuple(overrides), data.get("settings", {}), tuple(problems), skip, tuple(notices), classified, rejected)


# Compose files by name; a repo with many (one per service folder) still gets one `compose` table.
COMPOSE_FILES = ("compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml")


# A shell stack is two or more scripts, or one long enough to hold logic; a lone `exec` wrapper is not one.
# bd writes its own hook shims under .beads/hooks.
_SHELL_MIN_LINES = 10


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
        found["shell"] = scripts
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
    skip = state.skip
    declared_stacks = tuple(declared.get("stacks", ()))
    found: dict[str, list[str]] = {} if declared_stacks else _stack_files(repo, skip)
    stack_files = (
        tuple((s, f"declared in {STATE_FILE}") for s in declared_stacks)
        if declared_stacks
        else tuple((s, _evidence_files(files)) for s, files in found.items())
    )
    profile = Profile(
        kind=str(declared.get("kind") or _detect_kind(repo, skip)),
        surfaces=tuple(declared.get("surfaces", ())),
        traits=tuple(declared.get("traits", ())),
        stacks=declared_stacks or tuple(found),
        tracker="beads" if (repo / ".beads").is_dir() else declared.get("tracker"),
        frameworks=tuple((str(f), str(r)) for f, r in declared.get("frameworks", {}).items()) or detect_frameworks(repo, skip),
        stack_files=stack_files,
        ignore=skip,
    )
    facts, evidence = detect_facts(Context(repo, profile))
    # A declaration only adds: detected facts, classified claims and the simple declared values join; nothing is removed.
    claims = (*(f.claim for f in facts), *(j.claim for j in state.classified))
    return replace(
        profile,
        kind=profile.kind if declared.get("kind") else next((j.claim for j in state.classified if j.claim in KINDS), profile.kind),
        surfaces=_joined(profile.surfaces, claims, SURFACES),
        traits=_joined(profile.traits, claims, TRAITS),
        facts=facts,
        evidence=evidence,
        classified=state.classified,
        rejected=state.rejected,
    )


def _joined(declared: tuple[str, ...], claims: tuple[str, ...], among: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*declared, *(c for c in claims if c in among))))
