"""Stack: every detected stack has a profile, and each role in it is set up and run by the gate.

Profiles are data (`blueprint/profiles/<stack>.toml`), so a new stack is a file, not code. A stack
with no profile is itself a finding: research the tools for each role, write the profile in the
shelf, then the role rows can judge it.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from blueprint.concerns.gate import reachable_recipes
from blueprint.model import Finding, Sub, check_each, failing, not_applicable, not_checked, not_set_up, passing

if TYPE_CHECKING:
    from blueprint.model import Context

PROFILE_DIR = Path(__file__).resolve().parent.parent / "profiles"
# The roles every stack profile answers, and every framework profile on top of it. A profile that
# leaves a role out is a blueprint gap for that role, so the list is the research brief for a new one.
ROLES = (
    "toolchain",  # language/SDK version pinned in a file a script can read; lockfile committed
    "formatter",  # one opinionated formatter, checked in the gate
    "linter",  # the strictest current rule set or analyzers, warnings as errors
    "types",  # the type checker or nullability, strictest mode
    "dependencies",  # versions pinned centrally; unused/missing dependencies caught
    "tests",  # the test runner, headless, in the gate
    "coverage",  # a coverage floor that only rises
    "spelling",  # typos in code and docs
    "architecture",  # layer rules enforced by a tool (banned APIs, import rules)
    "hooks",  # what prek runs per commit for this stack (fast: format and lint on staged files)
    "agent-guidance",  # the stack's conventions file agents read (docs/agents/<stack>.md), linked from AGENTS.md
)
FRAMEWORK_ROLES = (
    "engine-version",  # the framework/engine version pinned in a file a script can read, the same everywhere
    "project-hygiene",  # generated folders ignored, required metadata committed, line endings fixed
    "assets",  # binary assets in LFS or kept out; import settings committed
    "scripts-lint",  # the framework's own script language linted, or `na` with the reason
    "build",  # the framework's build/import runs headless from `make check`
    "tests",  # in-framework tests (scenes, nodes), headless
    "scene-integrity",  # broken references between scenes and resources caught
    "architecture",  # the core stays framework-free; the framework layer is thin
    "ci",  # the framework runs in CI, version taken from the pin
    "hooks",  # what prek adds per commit for the framework
    "agent-guidance",  # the framework's conventions file agents read (docs/agents/<framework>.md)
)
_RESEARCH = (
    "research the tools for each role ({roles}) and write blueprint/profiles/{stack}.toml in the shelf "
    "(`blueprint lacks: profile for {stack}` bead); the rows for this stack stay unjudged until then"
)


@dataclass(frozen=True)
class Role:
    """One role in a profile: the tool, how to install it, what proves it is set up and that it runs."""

    role: str
    tool: str = ""
    install: str = ""
    config: tuple[dict[str, Any], ...] = ()
    gate: str = ""
    untested: str = ""
    na: str = ""


@dataclass(frozen=True)
class StackProfile:
    """A stack's answers, one per role."""

    stack: str
    status: str
    source: str
    roles: dict[str, Role] = field(default_factory=dict)


def load_profiles(directory: Path = PROFILE_DIR) -> dict[str, StackProfile]:
    """Every `<stack>.toml` in `directory`."""
    profiles: dict[str, StackProfile] = {}
    for path in sorted(directory.glob("*.toml")):  # frameworks/ is a subfolder, not read here
        data: dict[str, Any] = tomllib.loads(path.read_text())
        roles = {
            r["role"]: Role(
                role=r["role"],
                tool=r.get("tool", ""),
                install=r.get("install", ""),
                config=tuple(r.get("config", ())),
                gate=r.get("gate", ""),
                untested=r.get("untested", ""),
                na=r.get("na", ""),
            )
            for r in data.get("role", [])
        }
        profiles[data["stack"]] = StackProfile(data["stack"], data.get("status", "provisional"), data.get("source", ""), roles)
    return profiles


def gate_text(ctx: Context) -> str:
    """Everything `make check` reaches, plus a justfile and lefthook config if present."""
    parts = [reachable_recipes(ctx.read("Makefile") or "")]
    parts += [ctx.read(f) or "" for f in ("justfile", "Justfile", "lefthook.yml", "lefthook.yaml")]
    return "\n".join(parts)


def _config_holds(ctx: Context, spec: dict[str, Any], root: str = ".") -> bool:
    if "any" in spec:
        return any(_config_holds(ctx, alt, root) for alt in spec["any"])
    path = spec["path"].replace("{root}", root).removeprefix("./")
    if any(ch in path for ch in "*?["):
        return any(_config_holds(ctx, {**spec, "path": str(p.relative_to(ctx.repo))}) for p in sorted(ctx.repo.glob(path)))
    text = ctx.read(path)
    if text is None:
        return ctx.path(path).is_dir() and "contains" not in spec
    return spec.get("contains", "") in text


def _describe(spec: dict[str, Any]) -> str:
    if "any" in spec:
        return " or ".join(_describe(alt) for alt in spec["any"])
    return spec["path"] + (f" with {spec['contains']!r}" if "contains" in spec else "")


@dataclass(frozen=True)
class _Judged:
    stack: str
    verdict: str  # pass | not-set-up | failing | untested | na | no-profile
    evidence: str
    remediation: str = ""


def judge_role(ctx: Context, stack: str, profile: StackProfile | None, role: str, gate_text: str, root: str = ".") -> _Judged:
    if profile is None:
        return _Judged(stack, "no-profile", "no profile")
    spec = profile.roles.get(role)
    if spec is None or spec.untested:
        return _Judged(stack, "untested", f"no standard yet: {spec.untested if spec else 'the profile does not cover this role'}")
    if spec.na:
        return _Judged(stack, "na", spec.na)
    missing = [_describe(c).replace("{root}", root) for c in spec.config if not _config_holds(ctx, c, root)]
    if missing:
        return _Judged(stack, "not-set-up", f"{spec.tool} not set up (missing {'; '.join(missing)})", spec.install)
    if spec.gate and not re.search(re.escape(spec.gate), gate_text):
        return _Judged(
            stack,
            "failing",
            f"{spec.tool} set up, but `make check` never runs `{spec.gate}`",
            f"run `{spec.gate}` from `make check`",
        )
    return _Judged(stack, "pass", spec.tool + (f", run by the gate (`{spec.gate}`)" if spec.gate else ""))


def finding_for(judged: _Judged) -> Finding:
    if judged.verdict == "not-set-up":
        return not_set_up(judged.evidence, judged.remediation)
    if judged.verdict == "failing":
        return failing(judged.evidence, judged.remediation)
    if judged.verdict in {"untested", "no-profile"}:
        return not_checked(judged.evidence, f"write the {judged.stack} answer for this role in the shelf's profile", blueprint_gap=True)
    if judged.verdict == "na":
        return not_applicable(judged.evidence)
    return passing(judged.evidence)


def _profile_row(stack: str, prof: StackProfile | None) -> Sub:
    statement = f"the shelf has a profile for {stack}: the tool for every role"
    if prof is None:
        finding = not_checked(
            f"no standard for {stack} yet: blueprint has no profile, so no tool per role can be judged",
            _RESEARCH.format(roles=", ".join(ROLES), stack=stack),
            blueprint_gap=True,
        )
        return Sub(f"stack/{stack}", f"stack.{stack}.profile", statement, finding)
    tools = " · ".join(f"{r.role}: {r.tool or '(untested)'}" for r in prof.roles.values() if not r.na)
    note = "" if prof.status == "evidenced" else "; provisional: written, not yet proven in a second repo"
    return Sub(f"stack/{stack}", f"stack.{stack}.profile", statement, passing(f"{prof.status} profile: {tools}{note}"))


@check_each("stack.roles", "each stack's tool for each role, from its profile, is set up and run by `make check`", layer="stack")
def roles(ctx: Context) -> list[Sub]:
    """Per detected stack: one profile row, then one row per role."""
    if not ctx.profile.stacks:
        finding = not_checked(
            "no stack detected: no manifest the engine knows (pyproject.toml, *.csproj, go.mod, Cargo.toml, package.json)",
            "add the stack's detection to blueprint/profile.py in the shelf",
            blueprint_gap=True,
        )
        return [Sub("stack", "stack.detected", "the repo's stacks are detected", finding)]
    profiles = load_profiles()
    reached = gate_text(ctx)
    subs: list[Sub] = []
    for stack in ctx.profile.stacks:
        prof = profiles.get(stack)
        subs.append(_profile_row(stack, prof))
        if prof is None:
            continue
        for role in ROLES:
            judged = judge_role(ctx, stack, prof, role, reached)
            statement = f"{stack} {role}: the profile's tool is set up and run by `make check`"
            subs.append(Sub(f"stack/{stack}", f"stack.{stack}.{role}", statement, finding_for(judged)))
    return subs
