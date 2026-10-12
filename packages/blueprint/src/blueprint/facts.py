"""Facts and evidence about the repo (ADR 0026): what detection reports, and the agent classifies.

A Fact means one thing only. Evidence points without proving, with a confidence. Both name a kind, surface
or trait from the closed lists below, and say `where` they were read (`path:line`, or `path`). Nothing here
turns a checkpoint on yet: the report only lists them.

Workflow files are read line by line, not parsed: the repo has no YAML dependency, and the signals are
a few literal keys (`uses:`, `push:`, `schedule:`, `cron:`).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from fnmatch import fnmatch
from typing import TYPE_CHECKING, Literal

from blueprint.concerns.cli_parse import _scripts
from blueprint.concerns.gate import _workflows
from blueprint.concerns.secrets import _RULES, _sops_files
from blueprint.model import walk

if TYPE_CHECKING:
    from blueprint.model import Context, Profile

# The closed lists (ADR 0026); they grow by an ADR.
KINDS = ("library", "application", "infrastructure")
SURFACES = ("http-server", "mcp-server", "cli", "web-ui", "desktop-app", "game")
TRAITS = ("deployed", "ships-image", "holds-secrets", "stores-data", "llm-backed", "scheduled-jobs")
CLAIMS = (*KINDS, *SURFACES, *TRAITS)

Confidence = Literal["high", "low"]
DECIDERS = ("detected", "agent", "owner")
ACCEPTED, REJECTED, AWAITING = "accepted", "rejected", "awaiting judgement"


@dataclass(frozen=True)
class Fact:
    """Something detection read that means one thing only; `claim` is a kind, surface or trait."""

    claim: str
    where: str


@dataclass(frozen=True)
class Evidence:
    """Something detection read that points at a claim without proving it."""

    claim: str
    where: str
    confidence: Confidence


@dataclass(frozen=True)
class Judgement:
    """A recorded decision on a claim: `[[profile.classified]]` accepts it, `[[profile.rejected]]` rejects the evidence at `where`."""

    claim: str
    decided_by: str
    reason: str
    where: str = ""


def _file(where: str) -> str:
    """The file part of `path:line`."""
    head, sep, tail = where.rpartition(":")
    return head if sep and tail.isdigit() else where


def judgement_problem(kind: str, raw: object) -> tuple[Judgement | None, str | None]:
    """The decision a `[[profile.<kind>]]` entry records, or why it is refused (a claim off the closed lists, no reason...)."""
    if not isinstance(raw, dict):
        return None, f"a profile.{kind} entry is not a table"
    claim, reason = str(raw.get("claim", "")), str(raw.get("reason", ""))
    where, by = str(raw.get("where", "")), str(raw.get("decided_by", "agent"))
    if claim not in CLAIMS:
        lists = f"kinds {', '.join(KINDS)}; surfaces {', '.join(SURFACES)}; traits {', '.join(TRAITS)}"
        return None, f"profile.{kind} claim {claim!r} is not on the closed lists: {lists}"
    what = f"profile.{kind} {claim!r}"
    if not reason.strip():
        return None, f"{what} has no reason"
    if by not in DECIDERS:
        return None, f"{what}: decided_by {by!r} is not one of {', '.join(DECIDERS)}"
    if kind == "rejected" and not where.strip():
        return None, f"{what} needs where: the evidence it rejects (path:line)"
    return Judgement(claim, by, reason, where.strip()), None


def status(claim: str, where: str, *, evidence: bool, classified: tuple[Judgement, ...], rejected: tuple[Judgement, ...]) -> str:
    """Where one fact or piece of evidence stands: accepted (classified), rejected (evidence only), or awaiting judgement."""
    if any(j.claim == claim for j in classified):
        return ACCEPTED
    if evidence and any(j.claim == claim and _file(j.where) == _file(where) for j in rejected):
        return REJECTED
    return AWAITING


# Runtime dependencies that point at a surface or trait, each low: a client library carries the same dependency.
_DEPENDENCY_EVIDENCE = (
    ("mcp-server", ("mcp", "fastmcp", "fastmcp-slim")),
    ("http-server", ("fastapi", "starlette", "uvicorn", "aiohttp", "flask")),
    ("stores-data", ("sqlite*", "duckdb*", "aiosqlite", "sqlalchemy", "sqlmodel", "apsw")),
    ("llm-backed", ("anthropic", "openai", "anyllm")),
)
# A deploy step: a script named for deploying, or the usual deploy verbs. `ssh` alone is an access test, not a deploy.
_DEPLOY_STEP = re.compile(
    r"[\w/.-]*deploy[\w-]*\.(py|sh)\b|\b(make|just|task|npm run) deploy\b|\bkubectl apply\b|\bhelm (upgrade|install)\b|\bansible-playbook\b"
)
_DEPLOY_SECRET = re.compile(r"secrets\.\w*DEPLOY\w*", re.IGNORECASE)


def _where(rel: str, line: int) -> str:
    return f"{rel}:{line}"


def _workflow_files(ctx: Context) -> list[tuple[str, list[str]]]:
    return [(p.relative_to(ctx.repo).as_posix(), p.read_text(errors="replace").splitlines()) for p in _workflows(ctx)]


def _code(lines: list[str]) -> list[tuple[int, str]]:
    """`(line number, text)` of the lines that are not comments."""
    return [(n, ln) for n, ln in enumerate(lines, 1) if not ln.lstrip().startswith("#")]


def _indent(text: str) -> int:
    return len(text) - len(text.lstrip())


def _step(lines: list[tuple[int, str]], at: int) -> list[tuple[int, str]]:
    """The workflow step holding line index `at`: from its `- ` line to the next step or a shallower line."""
    start = at
    while start > 0 and not lines[start][1].lstrip().startswith("- "):
        start -= 1
    base = _indent(lines[start][1])
    end = start + 1
    while end < len(lines) and lines[end][1].strip() and _indent(lines[end][1]) > base:
        end += 1
    return lines[start:end]


def _push_steps(lines: list[str]) -> list[tuple[int, list[tuple[int, str]]]]:
    """Each `docker/build-push-action` step with `push: true`, as `(line, step lines)`, in a workflow that logs in to a registry."""
    code = _code(lines)
    if not any("docker/login-action" in t or "docker login" in t for _, t in code):
        return []
    found = []
    for i, (n, t) in enumerate(code):
        step = _step(code, i)
        if "docker/build-push-action" in t and any(re.match(r"\s*push:\s*true\s*(#.*)?$", s) for _, s in step):
            found.append((n, step))
    return found


def _ships_image(rel: str, lines: list[str]) -> list[Fact]:
    pushes = _push_steps(lines)
    return [Fact("ships-image", _where(rel, pushes[0][0]))] if pushes else []


def _option(step: list[tuple[int, str]], key: str) -> str:
    for _, t in step:
        if m := re.match(rf"\s*{key}:\s*(.+?)\s*(?:\s#.*)?$", t):
            return m.group(1).strip("\"'").removeprefix("./")
    return ""


def shipped_images(ctx: Context, dockerfiles: list[str]) -> dict[str, str]:
    """Which of `dockerfiles` a `push: true` step builds (ADR 0026), each with the `path:line` of that step.

    The step names its file by `file:`, else by `context:` (its `Dockerfile`), else the root one; a `${{ matrix.* }}`
    template matches every file its pattern fits.
    """
    from blueprint.concerns.stack import _names  # noqa: PLC0415 -- stack imports the model, not this module

    shipped: dict[str, str] = {}
    for rel, lines in _workflow_files(ctx):
        for n, step in _push_steps(lines):
            file = _option(step, "file")
            context = _option(step, "context").rstrip("/")
            named = file or (f"{context}/Dockerfile" if context and context != "." else "Dockerfile")
            for d in dockerfiles:
                if d not in shipped and (d == named or ("${{" in named and _names(named, d))):
                    shipped[d] = _where(rel, n)
    return shipped


def is_deployed(profile: Profile) -> bool:
    """Whether the repo is deployed: high-confidence deploy evidence, or the classified `deployed` trait (ADR 0026)."""
    return "deployed" in profile.traits or any(e.claim == "deployed" and e.confidence == "high" for e in profile.evidence)


def _scheduled(rel: str, lines: list[str]) -> list[Fact]:
    code = _code(lines)
    for i, (n, t) in enumerate(code):
        if re.match(r"\s*schedule:\s*$", t) and any("cron:" in s for _, s in code[i + 1 : i + 4]):
            return [Fact("scheduled-jobs", _where(rel, n))]
    return []


def _deployed(rel: str, lines: list[str]) -> list[Evidence]:
    """A deploy key secret and a deploy step in one workflow file (not per job: the signal is the pair)."""
    code = _code(lines)
    if not any(_DEPLOY_SECRET.search(t) for _, t in code):
        return []
    step = next((n for n, t in code if _DEPLOY_STEP.search(t)), None)
    return [Evidence("deployed", _where(rel, step), "high")] if step else []


def _console_scripts(ctx: Context) -> list[Fact]:
    if not _scripts(ctx):
        return []
    for p in ["pyproject.toml", *(q.relative_to(ctx.repo).as_posix() for q in walk(ctx.repo, "pyproject.toml", 4))]:
        for n, ln in enumerate((ctx.read(p) or "").splitlines(), 1):
            if ln.strip() == "[project.scripts]":
                return [Fact("cli", _where(p, n))]
    return [Fact("cli", "pyproject.toml")]


def _sops(ctx: Context) -> list[Fact]:
    found = [_RULES] if ctx.read(_RULES) is not None else (_sops_files(ctx) or [])[:1]
    return [Fact("holds-secrets", found[0])] if found else []


def _dependencies(ctx: Context) -> list[Evidence]:
    from blueprint.profile import _runtime_dependencies  # noqa: PLC0415 -- profile imports this module

    found: list[Evidence] = []
    for path in walk(ctx.repo, "pyproject.toml", 4):
        rel = path.relative_to(ctx.repo).as_posix()
        have = _runtime_dependencies(path)
        lines = path.read_text(errors="replace").splitlines()
        for claim, names in _DEPENDENCY_EVIDENCE:
            if hit := sorted(h for h in have if any(fnmatch(h, n) for n in names)):
                pattern = re.compile(rf"[\"']{re.escape(hit[0])}[\w\[\]<>=!~. ,;-]*[\"']", re.IGNORECASE)
                n = next((i for i, ln in enumerate(lines, 1) if pattern.search(ln)), 0)
                found.append(Evidence(claim, _where(rel, n) if n else rel, "low"))
    return found


def _named_volumes(ctx: Context) -> list[Evidence]:
    from blueprint.profile import COMPOSE_FILES  # noqa: PLC0415 -- profile imports this module

    for pattern in COMPOSE_FILES:
        for path in walk(ctx.repo, pattern, 3):
            lines = path.read_text(errors="replace").splitlines()
            for n, ln in enumerate(lines, 1):
                if ln.rstrip() == "volumes:" and n < len(lines) and lines[n].startswith((" ", "\t")) and lines[n].strip():
                    return [Evidence("stores-data", _where(path.relative_to(ctx.repo).as_posix(), n), "low")]
    return []


def detect_facts(ctx: Context) -> tuple[tuple[Fact, ...], tuple[Evidence, ...]]:
    """Every fact and piece of evidence the repo's files give, each once."""
    facts = [*_console_scripts(ctx), *_sops(ctx)]
    evidence = [*_dependencies(ctx), *_named_volumes(ctx)]
    for rel, lines in _workflow_files(ctx):
        facts += [*_ships_image(rel, lines), *_scheduled(rel, lines)]
        evidence += _deployed(rel, lines)
    return tuple(dict.fromkeys(facts)), tuple(dict.fromkeys(evidence))


def as_dict(
    facts: tuple[Fact, ...],
    evidence: tuple[Evidence, ...],
    classified: tuple[Judgement, ...] = (),
    rejected: tuple[Judgement, ...] = (),
) -> dict[str, list[dict[str, str]]]:
    """The JSON shape, under the report's `facts_and_evidence` key; each item says its status."""
    return {
        "facts": [
            {**asdict(f), "status": status(f.claim, f.where, evidence=False, classified=classified, rejected=rejected)} for f in facts
        ],
        "evidence": [
            {**asdict(e), "status": status(e.claim, e.where, evidence=True, classified=classified, rejected=rejected)} for e in evidence
        ],
    }


def to_classify(
    facts: tuple[Fact, ...], evidence: tuple[Evidence, ...], classified: tuple[Judgement, ...], rejected: tuple[Judgement, ...]
) -> list[str]:
    """The claims still awaiting judgement, each once, as `claim (where)`."""
    items = [(f.claim, f.where, False) for f in facts] + [(e.claim, e.where, True) for e in evidence]
    return [f"{c} (`{w}`)" for c, w, ev in items if status(c, w, evidence=ev, classified=classified, rejected=rejected) == AWAITING]


def lines(
    facts: tuple[Fact, ...],
    evidence: tuple[Evidence, ...],
    classified: tuple[Judgement, ...] = (),
    rejected: tuple[Judgement, ...] = (),
) -> list[str]:
    """The report's section body: facts first, then evidence with its confidence, each marked; rejected evidence is not listed again."""
    out: list[str] = []
    for f in facts:
        st = status(f.claim, f.where, evidence=False, classified=classified, rejected=rejected)
        out.append(f"- fact, {st}: {f.claim} (`{f.where}`)")
    for e in evidence:
        st = status(e.claim, e.where, evidence=True, classified=classified, rejected=rejected)
        if st != REJECTED:
            out.append(f"- evidence, {e.confidence} confidence, {st}: {e.claim} (`{e.where}`)")
    out += [f"- rejected: {j.claim} (`{j.where}`), by {j.decided_by}: {j.reason.strip()}" for j in rejected if _rejects(j, evidence)]
    out += [f"- accepted: {j.claim}, by {j.decided_by}: {j.reason.strip()}" for j in classified]
    pending = to_classify(facts, evidence, classified, rejected)
    if pending:
        out += ["", f"To classify ({len(pending)}), write each as `[[profile.classified]]` or `[[profile.rejected]]` in the state file:"]
        out += [f"- {p}" for p in pending]
    return out if facts or evidence or classified else ["- none detected"]


def _rejects(j: Judgement, evidence: tuple[Evidence, ...]) -> bool:
    """Whether a rejection still silences something now detected."""
    return any(e.claim == j.claim and _file(e.where) == _file(j.where) for e in evidence)
