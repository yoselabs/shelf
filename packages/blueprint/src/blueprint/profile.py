"""What the repo is: detected from its files, overridden by `docs/blueprint/blueprint.toml`."""

from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from blueprint.facts import KINDS, SURFACES, TRAITS, Judgement, detect_facts, judgement_problem, package_json
from blueprint.model import SKIP_DIRS, Context, Profile, dockerfiles, is_skipped, override_toml, walk
from blueprint.names import canonical_name

STATE_DIR = "docs/blueprint"
STATE_FILE = f"{STATE_DIR}/blueprint.toml"
OVERRIDE_CODES = ("test-data", "remediated", "not-applicable", "not-supported", "not-detected")


def justification_problem(what: str, reason: str, expires: date | None, adr_number: str) -> str | None:
    """Why an exception to a blueprint rule is not justified, or None.

    One rule for every exception (an override, an ignored path): a reason, and either an `expires` date
    (a temporary exception) or an `adr` citing the decision record that makes it durable (blueprint does not read it).
    """
    if not reason.strip():
        return f"{what} has no reason"
    if expires is None and not adr_number:
        return f"{what} needs an expires date, or an adr citing the decision record"
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
    decided_by: str = "unknown"
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

    declared: dict[str, Any]  # Any: parsed TOML, read key by key
    overrides: tuple[Override, ...]
    settings: dict[str, Any]  # Any: parsed TOML, per-check shapes differ
    problems: tuple[str, ...]
    # Paths detection and role globs skip: the justified `detection` overrides and the old `[[profile.ignore]]` entries.
    skip: tuple[str, ...] = ()
    # Not failures: an old shape still read, with the exact text to replace it.
    notices: tuple[str, ...] = ()
    # The justified classification: `[[profile.classified]]` and `[[profile.rejected]]`, the refused ones left out.
    classified: tuple[Judgement, ...] = ()
    rejected: tuple[Judgement, ...] = ()
    # `[[edge]]`: contact between two stacks in one repo, as (from, to, via) with the repo-relative contract file.
    edges: tuple[tuple[str, str, str], ...] = ()
    # `[plugins]`: one switch per plugin, `beads = false` (mission blueprint-plugins). Absent means the plugin's default.
    plugins: tuple[tuple[str, bool], ...] = ()


def _load_plugin_switches(data: dict[str, Any], problems: list[str]) -> tuple[tuple[str, bool], ...]:
    from blueprint.plugins import load_plugins  # noqa: PLC0415 -- plugins.py must not import profile.py back

    known = load_plugins()
    switches: list[tuple[str, bool]] = []
    for name, value in data.get("plugins", {}).items():
        if name not in known:
            problems.append(f"[plugins] {name!r} is not a plugin (known: {', '.join(sorted(known))})")
        elif not isinstance(value, bool):
            problems.append(f"[plugins] {name} must be true or false, not {value!r}")
        else:
            switches.append((name, value))
    return tuple(switches)


def _load_edges(data: dict[str, Any], problems: list[str]) -> tuple[tuple[str, str, str], ...]:
    edges: list[tuple[str, str, str]] = []
    for raw in data.get("edge", []):
        parts = tuple(str(raw.get(k, "")).strip() for k in ("from", "to", "via"))
        if not all(parts) or not str(raw.get("reason", "")).strip():
            problems.append(f"edge {dict(raw)!r} needs from, to (stacks), via (the contract file) and a reason")
        else:
            edges.append((parts[0], parts[1], parts[2]))
    return tuple(edges)


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


def _load_override(raw: dict[str, Any], problems: list[str]) -> Override | None:
    oid = str(raw.get("id", ""))
    if not oid:
        problems.append("an override has no id")
        return None
    scope = str(raw.get("scope", "")).strip()
    reason = str(raw.get("reason", ""))
    expires = _date_or_none(raw.get("expires"))
    adr_number = str(raw.get("adr", ""))
    # Missing means nobody recorded who decided; "agent" would claim it (a2kay 2026-10-12: an owner's yes read as agent).
    decided_by = str(raw.get("decided_by", "unknown"))
    what = f"override {oid!r}" + (f" ({scope})" if scope else "")
    unjustified = justification_problem(what, reason, expires, adr_number)
    if unjustified is None and decided_by not in (*DECIDERS, "unknown"):
        unjustified = f"{what}: decided_by {decided_by!r} is not one of {', '.join(DECIDERS)}"
    if unjustified is None and oid == DETECTION and not scope:
        unjustified = f"{what} needs a scope: the path glob detection skips"
    if unjustified:
        problems.append(unjustified)
    return Override(oid, reason, scope, str(raw.get("code", "")), decided_by, expires, adr_number, unjustified)


def _legacy_ignore(raw: dict[str, Any], today: date, problems: list[str]) -> tuple[Override | None, str]:
    """An old `[[profile.ignore]]` entry as the detection override it becomes, and the notice to move it."""
    path = str(raw.get("path", "")).strip()
    expires = _date_or_none(raw.get("expires"))
    adr_number = str(raw.get("adr", ""))
    why = str(raw.get("reason", ""))
    problem = (
        f"ignore entry has no path (reason: {why!r})" if not path else justification_problem(f"ignore {path!r}", why, expires, adr_number)
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
    overrides = [o for raw in data.get("override", []) if (o := _load_override(raw, problems)) is not None]
    declared = data.get("profile", {})
    notices: list[str] = []
    for raw in declared.get("ignore", []):
        legacy, notice = _legacy_ignore(raw, today, problems)
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
    edges = _load_edges(data, problems)
    switches = _load_plugin_switches(data, problems)
    return State(
        declared, tuple(overrides), data.get("settings", {}), tuple(problems), skip, tuple(notices), classified, rejected, edges, switches
    )


# Compose files by name; a repo with many (one per service folder) still gets one `compose` table.
COMPOSE_FILES = ("compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml")


# A shell stack is two or more scripts, or one long enough to hold logic; a lone `exec` wrapper is not one.
# bd writes its own hook shims under .beads/hooks.
_SHELL_MIN_LINES = 10


def _shell_scripts(repo: Path, skip: tuple[str, ...]) -> list[str]:
    found = walk(repo, "*.sh", 3, (*skip, ".beads/hooks"))
    if (
        len(found) == 1 and len(found[0].read_text(encoding="utf-8", errors="replace").splitlines()) < _SHELL_MIN_LINES
    ):  # lossy-ok: parse: the text is matched for a yes/no or one value, never stored or hashed
        return []
    return [p.relative_to(repo).as_posix() for p in found]


_NODE_CODE_TOOLS = frozenset({"typescript", "vitest", "jest", "mocha", "ava", "tap", "@playwright/test"})
_NODE_TEST_SCRIPT = re.compile(r"\b(?:test|vitest|jest|mocha|tsc)\b")


def _builds_tooling_only(manifest: Path) -> bool:
    """A package.json that only runs build tools: it has scripts, none tests or type-checks, no TypeScript or test runner is a dependency,
    and no tsconfig.json sits beside it. The code it serves is plain JS, tested by another stack's runner; the `node` profile (TypeScript,
    vitest) does not fit it. A manifest with no scripts is read as `node`, as before."""
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict) or (manifest.parent / "tsconfig.json").is_file():
        return False
    scripts = data.get("scripts")
    if not isinstance(scripts, dict) or not scripts:
        return False
    deps = {k for table in ("dependencies", "devDependencies") if isinstance(data.get(table), dict) for k in data[table]}
    return not _NODE_CODE_TOOLS & deps and not any(_NODE_TEST_SCRIPT.search(f"{k} {v}") for k, v in scripts.items())


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
        # Node manifests may sit two folders down (apps/web/package.json); never descend into dependency folders.
        if manifests := walk(repo, manifest, 3 if stack == "node" else 2, skip):
            files = sorted((p.relative_to(repo).as_posix() for p in manifests), key=lambda rel: (rel.count("/"), rel))
            found["node-tooling" if stack == "node" and _builds_tooling_only(repo / files[0]) else stack] = files
    if scripts := _shell_scripts(repo, skip):
        found["shell"] = scripts
    return found


def _stack_roots(found: dict[str, list[str]]) -> tuple[tuple[str, str], ...]:
    """The folder each stack's first manifest sits in; a stack that is not a single manifest (dotnet, nix, ...) is rooted at the repo."""
    return tuple((s, str(Path(files[0]).parent)) for s, files in found.items() if s in {"node", "node-tooling", "go", "rust"})


def detect_stacks(repo: Path, skip: tuple[str, ...] = ()) -> tuple[str, ...]:
    """The stacks present, from their manifests."""
    return tuple(_stack_files(repo, skip))


def detected_stack_roots(repo: Path) -> tuple[tuple[str, str], ...]:
    """The same manifest folders used by profile detection, for commands run in those stacks."""
    return _stack_roots(_stack_files(repo, ()))


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
        project = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("project", {})
    except (tomllib.TOMLDecodeError, OSError):
        return set()
    specs = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        specs += extra
    names = (re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", str(spec).strip()) for spec in specs)
    return {canonical_name(m.group()) for m in names if m}


def _source_uses(folder: Path, needles: tuple[str, ...]) -> bool:
    for here, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in _NOT_SOURCE]
        for name in files:
            if name.endswith(".py") and any(
                n in (Path(here) / name).read_text(encoding="utf-8", errors="replace") for n in needles
            ):  # lossy-ok: parse: the text is matched for a yes/no or one value, never stored or hashed
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
    if (repo / "package.json").is_file():
        manifest = package_json(repo / "package.json")
        if manifest.get("workspaces") and not manifest.get("bin"):
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
        stack_roots=_stack_roots(found),
        edges=state.edges,
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
