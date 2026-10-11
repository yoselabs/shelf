"""Stack: every detected stack has a profile, and each role in it is set up and run by the gate.

Profiles are data (`blueprint/profiles/<stack>.toml`), so a new stack is a file, not code. A stack
with no profile is itself a finding: research the tools for each role, write the profile in the
shelf, then the role rows can judge it.
"""

from __future__ import annotations

import json
import re
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from blueprint import gate_graph
from blueprint.model import Finding, Sub, check_each, failing, is_skipped, not_applicable, not_checked, not_set_up, passing

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
# Names are framework-neutral: a role says what is judged, and each profile maps its own tools onto it
# (godot: scenes and import settings; mcp: the tool list and its schema).
FRAMEWORK_ROLES = (
    "framework-version",  # the framework/engine/library version pinned in a file a script can read, the same everywhere
    "project-hygiene",  # generated folders ignored, required metadata committed, line endings fixed, protocol streams clean
    "binary-assets",  # binary assets in LFS or kept out; import settings committed
    "embedded-script-lint",  # a script language the framework embeds is linted, or `na` with the reason
    "build",  # the framework's build/import/serve smoke runs headless from `just check`
    "tests",  # tests run through the framework itself (scene tree, in-memory client), headless
    "surface-integrity",  # the surface the framework exposes (scene references, tool list) cannot drift unseen
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
    # Other ways to prove the role runs: each is a `label`, a `gate` regex over the gate text, and
    # optionally a `path`/`contains` the repo's config must also hold.
    alternatives: tuple[dict[str, Any], ...] = ()
    untested: str = ""
    na: str = ""
    # Where the role's executable may live, besides PATH: `$PATH`, `$DOTNET_ROOT` or an absolute folder. A
    # toolchain role names them when a second install can be the one a tool resolves (Godot's dotnet).
    installs: tuple[str, ...] = ()


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
                alternatives=tuple(r.get("alternative", ())),
                untested=r.get("untested", ""),
                na=r.get("na", ""),
                installs=tuple(r.get("installs", ())),
            )
            for r in data.get("role", [])
        }
        profiles[data["stack"]] = StackProfile(data["stack"], data.get("status", "provisional"), data.get("source", ""), roles)
    return profiles


def gate_text(ctx: Context) -> str:
    """Everything `just check` reaches (a Makefile's `check`, for one not yet migrated), the hook config it runs, lefthook's."""
    gate = gate_graph.load(ctx)
    parts = [gate.gate_recipes() if gate else ""]
    # Hooks the gate runs (`make lint` -> `pre-commit run --all-files`) are the gate's checks too (homelab, shelf-0kz).
    if gate_graph.HOOK_RUN.search(parts[0]):
        parts.append(ctx.read(gate_graph.HOOK_CONFIG) or "")
    parts += [ctx.read(f) or "" for f in ("lefthook.yml", "lefthook.yaml")]
    return "\n".join(parts)


def _config_holds(ctx: Context, spec: dict[str, Any], root: str = ".") -> bool:
    if "any" in spec:
        return any(_config_holds(ctx, alt, root) for alt in spec["any"])
    path = spec["path"].replace("{root}", root).removeprefix("./")
    if any(ch in path for ch in "*?["):
        hits = (p.relative_to(ctx.repo) for p in sorted(ctx.repo.glob(path)))
        return any(_config_holds(ctx, {**spec, "path": str(rel)}) for rel in hits if not is_skipped(rel.as_posix(), ctx.profile.ignore))
    text = ctx.read(path)
    if text is None:
        return ctx.path(path).is_dir() and "contains" not in spec
    return spec.get("contains", "") in text


def _offenders(ctx: Context, spec: dict[str, Any], root: str = ".") -> list[str]:
    """For a `lacks` entry: each file `path` matches that holds the forbidden text (an unpinned `:latest` image)."""
    path = spec["path"].replace("{root}", root).removeprefix("./")
    hits = sorted(ctx.repo.glob(path)) if any(ch in path for ch in "*?[") else [ctx.path(path)]
    rels = [h.relative_to(ctx.repo).as_posix() for h in hits if h.is_file()]
    return [r for r in rels if not is_skipped(r, ctx.profile.ignore) and spec["lacks"] in (ctx.read(r) or "")]


def _describe(spec: dict[str, Any]) -> str:
    if "any" in spec:
        return " or ".join(_describe(alt) for alt in spec["any"])
    return spec["path"] + (f" with {spec['contains']!r}" if "contains" in spec else "")


def _alternative_runs(ctx: Context, alt: dict[str, Any], gate_text: str) -> bool:
    if not re.search(alt["gate"], gate_text):
        return False
    return "path" not in alt or _config_holds(ctx, alt)


@dataclass(frozen=True)
class _Judged:
    stack: str
    verdict: str  # pass | not-set-up | failing | untested | na | no-profile
    evidence: str
    remediation: str = ""


def judge_role(ctx: Context, stack: str, profile: StackProfile | None, role: str, gate_text: str, *, root: str = ".") -> _Judged:
    if profile is None:
        return _Judged(stack, "no-profile", "no profile")
    spec = profile.roles.get(role)
    if spec is None or spec.untested:
        return _Judged(stack, "untested", f"no standard yet: {spec.untested if spec else 'the profile does not cover this role'}")
    if spec.na:
        return _Judged(stack, "na", spec.na)
    missing = [_describe(c).replace("{root}", root) for c in spec.config if "lacks" not in c and not _config_holds(ctx, c, root)]
    forbidden = [f"{hit} has {c['lacks']!r}" for c in spec.config if "lacks" in c for hit in _offenders(ctx, c, root)]
    if missing or forbidden:
        why = "; ".join([*([f"missing {'; '.join(missing)}"] if missing else []), *forbidden])
        return _Judged(stack, "not-set-up", f"{spec.tool} not set up ({why})", spec.install)
    judged = _gate_verdict(ctx, stack, spec, gate_text)
    if judged.verdict == "pass" and spec.installs and stack == "dotnet" and role == "toolchain":
        return _sdk_installs(ctx, stack, spec, judged)
    return judged


_SDK_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)")
# global.json rollForward -> how far from the requested SDK an installed one may be: 0 = same feature band,
# 1 = any band of the same major.minor, 2 = any minor of the same major, 3 = any major; `disable` is exact.
_ROLL_REACH = {"patch": 0, "latestpatch": 0, "feature": 1, "latestfeature": 1, "minor": 2, "latestminor": 2, "major": 3, "latestmajor": 3}


def _sdk_ok(want: tuple[int, int, int], have: tuple[int, int, int], roll: str) -> bool:
    """Whether an installed SDK satisfies `global.json`'s version under its rollForward policy (feature band = patch // 100)."""
    if roll.lower() == "disable":
        return have == want
    reach = _ROLL_REACH.get(roll.lower(), 0)
    if have < want:
        return False
    if reach == 0:
        return have[:2] == want[:2] and have[2] // 100 == want[2] // 100
    if reach == 1:
        return have[:2] == want[:2]
    return reach == 3 or have[0] == want[0]


def _dotnet_executables(ctx: Context, spec: Role) -> list[Path]:
    """Each distinct dotnet the tools may resolve: on PATH, under DOTNET_ROOT, in a well-known folder."""
    found: list[Path] = []
    for place in spec.installs:
        if place == "$PATH":
            exe = shutil.which("dotnet", path=ctx.env.get("PATH"))
            candidate = Path(exe) if exe else None
        elif place == "$DOTNET_ROOT":
            candidate = Path(ctx.env["DOTNET_ROOT"]) / "dotnet" if ctx.env.get("DOTNET_ROOT") else None
        else:
            candidate = ctx.system_path(place) / "dotnet"
        if candidate is not None and candidate.is_file() and candidate.resolve() not in {f.resolve() for f in found}:
            found.append(candidate)
    return found


def _sdk_versions(ctx: Context, exe: Path) -> list[tuple[int, int, int]]:
    done = ctx.run(str(exe), "--list-sdks", timeout=30)
    lines: list[str] = done.stdout.splitlines() if done is not None and done.returncode == 0 else []
    return [(int(m[1]), int(m[2]), int(m[3])) for line in lines if (m := _SDK_VERSION.match(line.strip()))]


def _sdk_installs(ctx: Context, stack: str, spec: Role, judged: _Judged) -> _Judged:
    """global.json must be satisfiable by an SDK of every dotnet install the tools may resolve.

    Why: lifesim pinned the SDK of the dotnet on PATH, and Godot's .NET editor resolved the other install,
    whose newer feature band the pin does not accept: `just build` passed, the editor's build exited 155.
    """
    try:
        sdk = json.loads(ctx.read("global.json") or "{}").get("sdk", {})
    except json.JSONDecodeError:
        return judged
    pin = _SDK_VERSION.match(str(sdk.get("version", "")))
    exes = _dotnet_executables(ctx, spec)
    if pin is None or not exes:
        return judged
    want, roll = (int(pin[1]), int(pin[2]), int(pin[3])), str(sdk.get("rollForward", "latestPatch"))
    listed = [(exe, _sdk_versions(ctx, exe)) for exe in exes]
    show = [f"{exe} (SDKs {', '.join('.'.join(map(str, v)) for v in versions) or 'none'})" for exe, versions in listed]
    lacking = [i for i, (_, versions) in enumerate(listed) if not any(_sdk_ok(want, v, roll) for v in versions)]
    if not lacking:
        return _Judged(
            stack, "pass", f"{judged.evidence}; global.json {sdk.get('version')} ({roll}) is met by {len(exes)} dotnet install(s)"
        )
    pinned = f"global.json pins {sdk.get('version')} (rollForward {roll})"
    return _Judged(
        stack,
        "failing",
        f"{pinned}: met by {', '.join(show[i] for i in range(len(show)) if i not in lacking) or 'no install'}, "
        f"but not by {', '.join(show[i] for i in lacking)}",
        "give every dotnet the tools resolve an SDK global.json accepts: upgrade the install that lacks it, pin a version "
        "all installs carry, or loosen rollForward (latestFeature); an install that is not meant to build can be removed",
    )


def _gate_verdict(ctx: Context, stack: str, spec: Role, gate_text: str) -> _Judged:
    """Pass when the gate runs the role's command, or one of its alternatives; else failing."""
    if not spec.gate or re.search(re.escape(spec.gate), gate_text):
        return _Judged(stack, "pass", spec.tool + (f", run by the gate (`{spec.gate}`)" if spec.gate else ""))
    via = next((a for a in spec.alternatives if _alternative_runs(ctx, a, gate_text)), None)
    if via is not None:
        return _Judged(stack, "pass", f"{via['label']}, run by the gate")
    others = "".join(f", or {a['label']}" for a in spec.alternatives)
    if not spec.config:
        # Nothing to find in the repo's files, so a gate that never runs the tool means nothing sets it up (shelf-8bi).
        return _Judged(
            stack,
            "not-set-up",
            f"{spec.tool} not set up: nothing in the repo configures it, and the gate never runs `{spec.gate}`{others}",
            spec.install or f"run `{spec.gate}` from `just check`{others}",
        )
    return _Judged(
        stack,
        "failing",
        f"{spec.tool} set up, but the gate never runs `{spec.gate}`{others}",
        f"run `{spec.gate}` from `just check`{others}",
    )


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


def _profile_row(stack: str, prof: StackProfile | None, origin: str = "") -> Sub:
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
    seen = f"; {stack} detected from {origin}" if origin else ""
    return Sub(f"stack/{stack}", f"stack.{stack}.profile", statement, passing(f"{prof.status} profile: {tools}{note}{seen}"))


@check_each("stack.roles", "each stack's tool for each role, from its profile, is set up and run by `just check`", layer="stack", version=3)
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
    origins = dict(ctx.profile.stack_files)
    subs: list[Sub] = []
    for stack in ctx.profile.stacks:
        prof = profiles.get(stack)
        origin = origins.get(stack, "") + (f"; ignored paths: {', '.join(ctx.profile.ignore)}" if ctx.profile.ignore else "")
        subs.append(_profile_row(stack, prof, origin))
        if prof is None:
            continue
        for role in ROLES:
            judged = judge_role(ctx, stack, prof, role, reached)
            statement = f"{stack} {role}: the profile's tool is set up and run by `just check`"
            subs.append(Sub(f"stack/{stack}", f"stack.{stack}.{role}", statement, finding_for(judged)))
    return subs
