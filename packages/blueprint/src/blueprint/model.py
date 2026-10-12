"""The result every check returns, and the registry checks join by decorator."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tomllib
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from blueprint.facts import Evidence, Fact
    from blueprint.profile import Override

# Never walked: tool caches, environments and build output hold no repo decisions, and a
# virtualenv alone can be gigabytes.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".pyrefly_cache",
        "worktrees",
        ".worktrees",
        ".turbo",
        ".hypothesis",
        "bin",
        "obj",
        "dist",
        "build",
        "target",
    }
)
# A Unity project's caches and per-user state, skipped only beside its ProjectSettings/: elsewhere a
# folder named Library can be source.
UNITY_CACHES = frozenset({"Library", "Temp", "Logs", "UserSettings"})


def toml_table(data: object, *keys: str) -> dict[str, object]:
    """The table at `keys` inside parsed TOML; empty when a key is missing or not a table."""
    for key in keys:
        data = data.get(key) if isinstance(data, dict) else None
    return data if isinstance(data, dict) else {}


def is_skipped(rel: str, skip: tuple[str, ...]) -> bool:
    """Whether the repo-relative slash path `rel` is, or lies under, one of the `skip` paths (a folder or a glob)."""
    return any(fnmatch(rel, p.rstrip("/")) or rel.startswith(p.rstrip("/") + "/") for p in skip)


def walk(root: Path, pattern: str, max_depth: int | None = None, skip: tuple[str, ...] = ()) -> list[Path]:
    """Files under `root` matching `pattern`, skipping SKIP_DIRS and the repo-declared `skip` paths, at most `max_depth` levels down."""
    found: list[Path] = []
    for here, dirs, files in os.walk(root):
        depth = len(Path(here).relative_to(root).parts)
        dirs[:] = [
            d
            for d in dirs
            if d not in SKIP_DIRS
            and not (d in UNITY_CACHES and (Path(here) / "ProjectSettings").is_dir())
            and (max_depth is None or depth + 1 < max_depth)
            and not is_skipped((Path(here) / d).relative_to(root).as_posix(), skip)
        ]
        found += [
            Path(here) / f for f in files if fnmatch(f, pattern) and not is_skipped((Path(here) / f).relative_to(root).as_posix(), skip)
        ]
    return sorted(found)


# Image build files by name: `Dockerfile`, `test.Dockerfile`, `Dockerfile.dev`, `Containerfile`; not their `.dockerignore`.
DOCKERFILES = ("Dockerfile", "*.Dockerfile", "Dockerfile.*", "Containerfile")


def dockerfiles(root: Path, skip: tuple[str, ...] = ()) -> list[Path]:
    """The image build files within three levels of `root`."""
    found = {p for pattern in DOCKERFILES for p in walk(root, pattern, 3, skip) if not p.name.endswith(".dockerignore")}
    return sorted(found)


# What a check tells the owner when it finds an old in-file marker.
MOVE = "move this to an [[override]] in docs/blueprint/blueprint.toml"


def override_toml(
    oid: str, scope: str, reason: str, *, decided_by: str = "agent", expires: date | None = None, adr_number: str = ""
) -> str:
    """The `[[override]]` table to paste into blueprint.toml."""
    lines = ["[[override]]", f"id = {json.dumps(oid)}"]
    if scope:
        lines.append(f"scope = {json.dumps(scope)}")
    lines += [f"reason = {json.dumps(reason)}", f"decided_by = {json.dumps(decided_by)}"]
    lines.append(f"expires = {expires.isoformat()}" if expires is not None else f"adr = {json.dumps(adr_number)}")
    return "\n".join(lines)


class Verdict(StrEnum):
    """What one run recorded for one checkpoint (CONTEXT.md: verdict)."""

    NOT_SET_UP = "not set up"
    FAILING = "failing"
    PASSING = "passing"
    NOT_APPLICABLE = "not applicable"
    NOT_CHECKED = "not checked"


class FixedBy(StrEnum):
    """Who applies the remediation: the engine (`blueprint fix`), an agent, or the owner."""

    AUTO = "auto"
    AGENT = "agent"
    OWNER = "owner"


@dataclass(frozen=True)
class Finding:
    """What a check saw. `set_up`/`working` are None when the check could not tell."""

    set_up: bool | None
    working: bool | None
    evidence: str
    remediation: str = ""
    fixed_by: FixedBy = FixedBy.AGENT
    applicable: bool = True
    # The blueprint itself cannot judge this yet (a stack with no profile, a role its profile leaves
    # untested). Reported every run, never a pass, but not the repo's fault: the exit code ignores it.
    blueprint_gap: bool = False

    @property
    def verdict(self) -> Verdict:
        """The verdict the two answers give."""
        if not self.applicable:
            return Verdict.NOT_APPLICABLE
        if self.set_up is None:
            return Verdict.NOT_CHECKED
        if not self.set_up:
            return Verdict.NOT_SET_UP
        if self.working is None:
            return Verdict.NOT_CHECKED
        return Verdict.PASSING if self.working else Verdict.FAILING


def passing(evidence: str) -> Finding:
    """Set up and working."""
    return Finding(set_up=True, working=True, evidence=evidence)


def failing(evidence: str, remediation: str, fixed_by: FixedBy = FixedBy.AGENT) -> Finding:
    """Set up, not working."""
    return Finding(set_up=True, working=False, evidence=evidence, remediation=remediation, fixed_by=fixed_by)


def not_set_up(evidence: str, remediation: str, fixed_by: FixedBy = FixedBy.AGENT) -> Finding:
    """Absent."""
    return Finding(set_up=False, working=None, evidence=evidence, remediation=remediation, fixed_by=fixed_by)


def not_checked(reason: str, remediation: str = "", fixed_by: FixedBy = FixedBy.AGENT, *, blueprint_gap: bool = False) -> Finding:
    """The check could not run; the reason is the evidence. Never a pass."""
    return Finding(set_up=None, working=None, evidence=reason, remediation=remediation, fixed_by=fixed_by, blueprint_gap=blueprint_gap)


def not_applicable(reason: str) -> Finding:
    """The checkpoint does not concern this repo."""
    return Finding(set_up=None, working=None, evidence=reason, applicable=False)


@dataclass(frozen=True)
class Profile:
    """What the repo is (CONTEXT.md: repo kind, surface, trait, stack profile)."""

    kind: str
    surfaces: tuple[str, ...]
    traits: tuple[str, ...]
    stacks: tuple[str, ...]
    tracker: str | None
    # Frameworks on top of a stack (a game engine, a web framework), each with the folder it lives in
    # relative to the repo root: (("godot", "src/Game.Godot"),).
    frameworks: tuple[tuple[str, str], ...] = ()
    # Each detected stack with the files that set it (or "declared in docs/blueprint/blueprint.toml"), so a
    # wrong stack can be traced to the file that caused it.
    stack_files: tuple[tuple[str, str], ...] = ()
    # Paths the repo declared throwaway or vendored (a `detection` [[override]]): detection and role globs skip them.
    ignore: tuple[str, ...] = ()
    # What detection read (blueprint.facts): reported, not yet acted on. Declared surfaces and traits stay as declared.
    facts: tuple[Fact, ...] = ()
    evidence: tuple[Evidence, ...] = ()


def uses_beads(profile: Profile) -> bool:
    """Whether the repo tracks its work in beads (an `applies` predicate)."""
    return profile.tracker == "beads"


# Set by git for a hook (the pre-push gate runs blueprint): inherited, they send every `git` blueprint runs, a sandbox's
# `git init` included, to the hook's repository instead of the folder it runs in. From a worktree that set core.bare on
# the main clone (2026-10-12). Each check finds its repo by its cwd instead.
_GIT_LOCATION = frozenset(
    {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY", "GIT_NAMESPACE"}
)


def without_git_location(env: Mapping[str, str]) -> dict[str, str]:
    """`env` minus the variables that pin git to one repository: each git call finds its own from its cwd."""
    return {k: v for k, v in env.items() if k not in _GIT_LOCATION}


@dataclass
class Context:
    """What a check reads through: the repo, its profile, and processes run with a timeout."""

    repo: Path
    profile: Profile
    env: dict[str, str] = field(default_factory=lambda: dict(os.environ))
    settings: dict[str, object] = field(default_factory=dict)
    # Every [[override]] of docs/blueprint/blueprint.toml, and the day it is judged on (an expired one excuses nothing).
    overrides: tuple[Override, ...] = ()
    today: date | None = None
    # Old shapes a check still honoured, each with the text that replaces it: reported, never failing (Run.notices).
    notices: list[str] = field(default_factory=list)

    def excused(self, checkpoint_id: str, path: str | None = None, line: int | None = None, service: str | None = None) -> Override | None:
        """The justified, unexpired, scoped override that excuses this offender of `checkpoint_id`, or None.

        A check asks per offender (a file, a line, a compose service) and drops the ones excused, then names the
        override in its evidence. An override without a scope is not asked here: the runner applies it to the whole row.
        """
        day = self.today or date.today()  # noqa: DTZ011 -- override expiry is a calendar date in the owner's zone
        return next(
            (o for o in self.overrides if o.id == checkpoint_id and o.problem(day) is None and o.covers(path, line, service)),
            None,
        )

    def expiry_hint(self, days: int = 180) -> date:
        """A date to put in the override a check tells the owner to write: a temporary exception, `days` out."""
        return (self.today or date.today()) + timedelta(days=days)  # noqa: DTZ011 -- a calendar date in the owner's zone

    def system_path(self, absolute: str) -> Path:
        """An absolute machine path (`/usr/local/share/dotnet`), under BLUEPRINT_SYSTEM_ROOT when a test sets one.

        Why: a check that looks at well-known install locations would otherwise judge the developer's own machine.
        """
        return Path(self.env.get("BLUEPRINT_SYSTEM_ROOT", "/")) / absolute.lstrip("/")

    def path(self, rel: str) -> Path:
        """`rel` inside the repo."""
        return self.repo / rel

    def read(self, rel: str) -> str | None:
        """The text of `rel`, or None when it is not a file."""
        p = self.repo / rel
        return p.read_text(errors="replace") if p.is_file() else None

    def toml(self, rel: str) -> dict[str, object]:
        """The parsed TOML file `rel`; empty when it is absent or not valid TOML (the checks that need it report that themselves)."""
        try:
            return tomllib.loads(self.read(rel) or "")
        except tomllib.TOMLDecodeError:
            return {}

    def has(self, tool: str) -> bool:
        """Whether `tool` is on this context's PATH."""
        return shutil.which(tool, path=self.env.get("PATH")) is not None

    def run(
        self, *argv: str, timeout: float = 120, cwd: Path | None = None, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str] | None:
        """Run `argv` in the repo (or `cwd`), with this context's env or `env`; None when the program is missing or times out."""
        env = without_git_location(env or self.env)
        exe = shutil.which(argv[0], path=env.get("PATH"))
        if exe is None:
            return None
        try:
            return subprocess.run(
                [exe, *argv[1:]],
                cwd=cwd or self.repo,
                env=env,
                capture_output=True,
                text=True,
                errors="replace",  # a tool's output (a binary blob, a non-UTF-8 log) never crashes a check
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return None

    def git(self, *args: str) -> str | None:
        """stdout of a git command, or None when it failed."""
        done = self.run("git", *args)
        return done.stdout if done is not None and done.returncode == 0 else None


# What part of the setup a concern judges: generic (any repo), stack (one language's tools),
# framework (an engine or framework on top of a stack), or agent (the agent harness: instructions,
# session settings, session hooks). Reports group by it.
LAYERS = ("generic", "stack", "framework", "agent")


@dataclass(frozen=True)
class Sub:
    """One row a multi-row check emits: its own concern label, id and statement."""

    concern: str
    id: str
    statement: str
    finding: Finding


@dataclass(frozen=True)
class Check:
    """One checkpoint's script: `run` decides its verdict, or, for a multi-row check, one per `Sub`.

    `audit_only`: left out of the per-commit gate (`--gate` without `--audit`), because it is slow or reads
    state only the developer's own clone has (bd's database, installed hooks).
    """

    id: str
    concern: str
    statement: str
    run: Callable[[Context], Finding | list[Sub]]
    version: int = 1
    audit_only: bool = False
    applies: Callable[[Profile], bool] = lambda _profile: True
    layer: str = "generic"


REGISTRY: list[Check] = []


def check(
    id: str,  # noqa: A002 -- the checkpoint's own word for it
    statement: str,
    *,
    version: int = 1,
    audit_only: bool = False,
    applies: Callable[[Profile], bool] = lambda _profile: True,
    layer: str = "generic",
) -> Callable[[Callable[[Context], Finding]], Callable[[Context], Finding]]:
    """Register the decorated function as checkpoint `id` (`<concern>.<name>`)."""

    def register(fn: Callable[[Context], Finding]) -> Callable[[Context], Finding]:
        concern = id.split(".", 1)[0]
        REGISTRY.append(
            Check(id=id, concern=concern, statement=statement, run=fn, version=version, audit_only=audit_only, applies=applies, layer=layer)
        )
        return fn

    return register


def check_each(
    id: str,  # noqa: A002 -- the checkpoint family's own word for it
    statement: str,
    *,
    version: int = 1,
    audit_only: bool = False,
    applies: Callable[[Profile], bool] = lambda _profile: True,
    layer: str = "generic",
) -> Callable[[Callable[[Context], list[Sub]]], Callable[[Context], list[Sub]]]:
    """Register a function that emits several rows, each with its own concern and id (one per stack)."""

    def register(fn: Callable[[Context], list[Sub]]) -> Callable[[Context], list[Sub]]:
        REGISTRY.append(
            Check(
                id=id,
                concern=id.split(".", 1)[0],
                statement=statement,
                run=fn,
                version=version,
                audit_only=audit_only,
                applies=applies,
                layer=layer,
            )
        )
        return fn

    return register
