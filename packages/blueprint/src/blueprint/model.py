"""The result every check returns, and the registry checks join by decorator."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

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


def walk(root: Path, pattern: str, max_depth: int | None = None) -> list[Path]:
    """Files under `root` whose name matches `pattern`, skipping SKIP_DIRS, at most `max_depth` levels down."""
    found: list[Path] = []
    for here, dirs, files in os.walk(root):
        depth = len(Path(here).relative_to(root).parts)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and (max_depth is None or depth + 1 < max_depth)]
        found += [Path(here) / f for f in files if fnmatch(f, pattern)]
    return sorted(found)


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


def uses_beads(profile: Profile) -> bool:
    """Whether the repo tracks its work in beads (an `applies` predicate)."""
    return profile.tracker == "beads"


@dataclass
class Context:
    """What a check reads through: the repo, its profile, and processes run with a timeout."""

    repo: Path
    profile: Profile
    env: dict[str, str] = field(default_factory=lambda: dict(os.environ))
    settings: dict[str, object] = field(default_factory=dict)

    def path(self, rel: str) -> Path:
        """`rel` inside the repo."""
        return self.repo / rel

    def read(self, rel: str) -> str | None:
        """The text of `rel`, or None when it is not a file."""
        p = self.repo / rel
        return p.read_text(errors="replace") if p.is_file() else None

    def has(self, tool: str) -> bool:
        """Whether `tool` is on this context's PATH."""
        return shutil.which(tool, path=self.env.get("PATH")) is not None

    def run(self, *argv: str, timeout: float = 120, cwd: Path | None = None) -> subprocess.CompletedProcess[str] | None:
        """Run `argv` in the repo; None when the program is missing or the timeout passes."""
        exe = shutil.which(argv[0], path=self.env.get("PATH"))
        if exe is None:
            return None
        try:
            return subprocess.run(
                [exe, *argv[1:]], cwd=cwd or self.repo, env=self.env, capture_output=True, text=True, timeout=timeout, check=False
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
    layer: str = "generic",
) -> Callable[[Callable[[Context], list[Sub]]], Callable[[Context], list[Sub]]]:
    """Register a function that emits several rows, each with its own concern and id (one per stack)."""

    def register(fn: Callable[[Context], list[Sub]]) -> Callable[[Context], list[Sub]]:
        REGISTRY.append(Check(id=id, concern=id.split(".", 1)[0], statement=statement, run=fn, version=version, layer=layer))
        return fn

    return register
