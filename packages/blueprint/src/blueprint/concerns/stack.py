"""Stack: every detected stack has a profile, and each role in it is set up and run by the gate.

Profiles are data (`blueprint/profiles/<stack>.toml`), so a new stack is a file, not code. A stack
with no profile is itself a finding: research the tools for each role, write the profile in the
shelf, then the role rows can judge it.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from blueprint import gate_graph, gate_test, gate_units
from blueprint.concerns.profile_data import Role, StackProfile, load_profiles
from blueprint.model import (
    Finding,
    FixedBy,
    Sub,
    Verdict,
    check_each,
    dockerfiles,
    failing,
    is_skipped,
    not_applicable,
    not_checked,
    not_set_up,
    passing,
)

if TYPE_CHECKING:
    from blueprint.model import Context

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
    "hooks",  # what prek adds per commit for the framework
)
_NA_NOT_ROWS = frozenset({"coverage", "embedded-script-lint"})


def is_checkpoint(profile: StackProfile, role: str) -> bool:
    """Whether a role of this profile becomes a row: not a cut role, and not a cut role the profile marks `na`."""
    spec = profile.roles.get(role)
    return not (role in _NA_NOT_ROWS and spec is not None and bool(spec.na or spec.untested))


_RESEARCH = (
    "research the tools for each role ({roles}) and write blueprint/profiles/{stack}.toml in the shelf "
    "(`blueprint lacks: profile for {stack}` bead); the rows for this stack stay unjudged until then"
)


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
    if spec.get("test-coverage"):
        return bool(gate_units.read_config(ctx.repo).coverage)
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


_DOCKER_BUILD = re.compile(r"\bdocker(?:\s+buildx)?\s+build\b")


def builds(gate: str, rel: str) -> bool:
    """Whether some command in `gate` is a `docker build` (or `docker buildx build`) that names the Dockerfile `rel`.

    `docker build --check` counts: BuildKit parses and lints the file (a syntax or rule error fails), though it runs no layer, so a
    failing `RUN` is found only by a full build. A path in a comment, an `echo` or another command counts for nothing.
    """
    logical = gate.replace("\\\n", " ")
    return any(_DOCKER_BUILD.search(line) and re.search(rf"(?<![\w./-]){re.escape(rel)}(?![\w./-])", line) for line in logical.splitlines())


def _unbuilt(ctx: Context) -> list[str]:
    """The Dockerfiles no `docker build` in the gate names."""
    gate = gate_text(ctx)
    return [r for r in _dockerfile_rels(ctx) if not builds(gate, r)]


def _dockerfile_rels(ctx: Context) -> list[str]:
    return [p.relative_to(ctx.repo).as_posix() for p in dockerfiles(ctx.repo, ctx.profile.ignore)]


_PURPOSE_FACT = {
    "shipped-image": "the repo ships an image: a classified ships-image trait and a Dockerfile",
    "deployed": "the repo is deployed: a classified deployed trait",
}


def purpose_fact(requires: str) -> str:
    """The fact that turns a purpose row on, for `blueprint check --list` and the not-applicable reason."""
    return _PURPOSE_FACT[requires]


def _purpose(ctx: Context, requires: str) -> tuple[bool, str]:
    """Whether the fact holds, and what it is about: the shipped images, or the classified trait."""
    from blueprint.facts import is_deployed  # noqa: PLC0415 -- facts imports the concerns

    if requires == "shipped-image":
        images = _dockerfile_rels(ctx) if "ships-image" in ctx.profile.traits else []
        return bool(images), ", ".join(images)
    return is_deployed(ctx.profile), "classified trait" if is_deployed(ctx.profile) else ""


def _describe(spec: dict[str, Any]) -> str:
    if "any" in spec:
        return " or ".join(_describe(alt) for alt in spec["any"])
    return str(spec["path"]) + (f" with {spec['contains']!r}" if "contains" in spec else "")


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
    if spec.requires:
        applies, about = _purpose(ctx, spec.requires)
        if not applies:
            return _Judged(stack, "na", f"not applicable here: it applies to {purpose_fact(spec.requires)}, and none is found")
        judged = _judge_set_up(ctx, stack, spec, role, gate_text, root=root)
        return replace(judged, evidence=f"{judged.evidence} [{spec.requires}: {about}]")
    return _judge_set_up(ctx, stack, spec, role, gate_text, root=root)


def _judge_set_up(ctx: Context, stack: str, spec: Role, role: str, gate_text: str, *, root: str) -> _Judged:
    plain = [c for c in spec.config if not {"lacks", "built"} & c.keys()]
    missing = [_describe(c).replace("{root}", root) for c in plain if not _config_holds(ctx, c, root)]
    missing += [f"nothing builds {r}" for c in spec.config if "built" in c for r in _unbuilt(ctx)]
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
    if spec.outcome:
        return _outcome_verdict(ctx, stack, spec, gate_text)
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


OUTCOMES = ("runs", "floor")


def _floor_holds(ctx: Context, floor: dict[str, Any], gate_text: str) -> bool:
    if floor.get("units"):
        config = gate_units.load(ctx.repo)
        if gate_test.is_workspace(ctx.repo) or config is None or not config.coverage or config.floor is None:
            return False
    return bool(re.search(floor["gate"], gate_text)) and ("path" not in floor or _config_holds(ctx, floor))


def _outcome_verdict(ctx: Context, stack: str, spec: Role, gate_text: str) -> _Judged:
    """Judge a role by its outcome: a test runner is reached, or a floor is enforced, by any tool the profile accepts."""
    if spec.outcome == "runs":
        if any(re.search(pattern, gate_text) for pattern in spec.runs):
            return _Judged(stack, "pass", f"{spec.tool}; the gate reaches a test runner")
        problem, fix = f"the gate reaches no test runner (accepted: {', '.join(spec.runs)})", "run the tests from `just check`"
    else:
        if via := next((f for f in spec.floors if _floor_holds(ctx, f, gate_text)), None):
            return _Judged(stack, "pass", f"{via['label']}, run by the gate")
        accepted = " or ".join(f["label"] for f in spec.floors)
        problem, fix = f"the gate enforces no floor (accepted: {accepted})", f"enforce a floor from `just check`: {accepted}"
    verdict = "failing" if spec.config else "not-set-up"
    return _Judged(stack, verdict, f"{spec.tool}: {problem}", spec.install or fix if verdict == "not-set-up" else fix)


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


_UNPROVEN = "unproven-standard: "


def provisional_finding(status: str, finding: Finding) -> Finding:
    """A red row from a provisional profile is the owner's to fix, its standard named unproven.

    Why: a provisional recipe applied on a blanket yes broke lifesim clones (shelf-o5a: a tool pin
    that broke git clone) and package compiles (shelf-ir7: a csc.rsp that hit packages); until the
    profile is evidenced in a second repo, each red row needs the owner's own decision, so its
    evidence and remediation carry the prefix and `fixed_by` is the owner's. Every other verdict —
    passing, not applicable, not checked, a blueprint gap — passes through unchanged.
    """
    if status == "evidenced" or finding.verdict not in {Verdict.FAILING, Verdict.NOT_SET_UP}:
        return finding
    return replace(
        finding,
        evidence=_UNPROVEN + finding.evidence,
        remediation=_UNPROVEN + finding.remediation if finding.remediation else finding.remediation,
        fixed_by=FixedBy.OWNER,
    )


def _profile_row(stack: str, prof: StackProfile | None, origin: str = "") -> Sub:
    statement = f"the shelf has a profile for {stack}: the tool for every role"
    if prof is None:
        # An error, never silence and never a pass (owner, 2026-11-19); a justified override is the only way past.
        finding = failing(
            f"stack {stack} found, no profile: blueprint has no tool per role for it, so the repo's {stack} code is unjudged",
            _RESEARCH.format(roles=", ".join(ROLES), stack=stack)
            + "; or record a justified `not-supported` override with an expiry or an accepted ADR",
        )
        return Sub(f"stack/{stack}", f"stack.{stack}.profile", statement, finding)
    tools = " · ".join(f"{r.role}: {r.tool or '(untested)'}" for r in prof.roles.values() if not r.na)
    note = "" if prof.status == "evidenced" else "; provisional: written, not yet proven in a second repo"
    seen = f"; {stack} detected from {origin}" if origin else ""
    return Sub(f"stack/{stack}", f"stack.{stack}.profile", statement, passing(f"{prof.status} profile: {tools}{note}{seen}"))


@check_each("stack.roles", "each stack's tool for each role, from its profile, is set up and run by `just check`", layer="stack", version=4)
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
    roots = dict(ctx.profile.stack_roots)
    subs: list[Sub] = []
    for stack in ctx.profile.stacks:
        prof = profiles.get(stack)
        origin = origins.get(stack, "") + (f"; ignored paths: {', '.join(ctx.profile.ignore)}" if ctx.profile.ignore else "")
        subs.append(_profile_row(stack, prof, origin))
        if prof is None:
            continue
        for role in (*ROLES, *(r for r in prof.roles if r not in ROLES)):
            if not is_checkpoint(prof, role):
                continue
            judged = judge_role(ctx, stack, prof, role, reached, root=roots.get(stack, "."))
            statement = f"{stack} {role}: the profile's tool is set up and run by `just check`"
            subs.append(Sub(f"stack/{stack}", f"stack.{stack}.{role}", statement, provisional_finding(prof.status, finding_for(judged))))
    if edges := _edges_row(ctx):
        subs.append(edges)
    return subs


def _edges_row(ctx: Context) -> Sub | None:
    """Two code stacks in one repo touch only through a declared `[[edge]]` (from, to, via a contract file that exists)."""
    profiles = load_profiles()
    # A language stack, or one with no profile yet (python without a lock): code that can call across a language boundary.
    present = [s for s in ctx.profile.stacks if s not in profiles or profiles[s].family == "language"]
    if len(present) < 2:
        return None
    statement = "stacks sharing the repo touch only through a declared [[edge]] with a contract file"
    edges = ctx.profile.edges
    if not edges:
        finding = not_set_up(
            f"{' and '.join(present)} share the repo and no [[edge]] says how they touch",
            "declare each contact in docs/blueprint/blueprint.toml: [[edge]] from = <stack>, to = <stack>, via = <contract file>, "
            "reason = <why>; an undeclared cross-stack path selects every test",
        )
        return Sub("stack", "stack.edges", statement, finding)
    problems = [f"edge {f} -> {t} names {s}, not a stack of this repo" for f, t, _ in edges for s in (f, t) if s not in present]
    problems += [f"edge {f} -> {t}: contract file {via} is missing" for f, t, via in edges if not ctx.path(via).exists()]
    if problems:
        return Sub(
            "stack", "stack.edges", statement, failing("; ".join(problems), "fix or delete the [[edge]] in docs/blueprint/blueprint.toml")
        )
    return Sub("stack", "stack.edges", statement, passing("; ".join(f"{f} -> {t} via {via}" for f, t, via in edges)))
