"""Facts and evidence about the repo (ADR 0026): what detection reports, and the agent classifies.

A Fact means one thing only. Evidence points without proving, with a confidence. Both name a kind, surface
or trait from the closed lists below, and say `where` they were read (`path:line`, or `path`). Nothing here
turns a checkpoint on yet: the report only lists them.

No repository has CI (ADR 0027), so no workflow file is read: `ships-image`, `deployed` and `scheduled-jobs`
are traits the agent classifies, not facts detection finds.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from fnmatch import fnmatch
from typing import TYPE_CHECKING, Literal

from blueprint.concerns.secrets.secrets import _RULES, _sops_files
from blueprint.concerns.stacks.cli_parse import _scripts
from blueprint.model import walk

if TYPE_CHECKING:
    from pathlib import Path

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
# The same, for a Node package: names in `dependencies` and `optionalDependencies` (dev and peer groups are left out).
_NODE_DEPENDENCY_EVIDENCE = (
    ("mcp-server", ("@modelcontextprotocol/sdk", "fastmcp")),
    ("http-server", ("express", "fastify", "koa", "hono", "@nestjs/core")),
    (
        "stores-data",
        ("better-sqlite3", "sqlite3", "pg", "mysql2", "mongodb", "mongoose", "ioredis", "@prisma/client", "drizzle-orm", "duckdb"),
    ),
    ("llm-backed", ("@anthropic-ai/sdk", "openai", "ai", "@ai-sdk/*", "langchain", "@langchain/*")),
)


def _where(rel: str, line: int) -> str:
    return f"{rel}:{line}"


def is_deployed(profile: Profile) -> bool:
    """Whether the repo is deployed: the classified `deployed` trait (ADR 0026; no workflow shows a deploy, ADR 0027)."""
    return "deployed" in profile.traits


def package_json(path: Path) -> dict[str, object]:
    """A package.json as a dict; an unreadable or non-object file is empty."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _package_runtime_dependencies(data: dict[str, object]) -> set[str]:
    groups = (data.get("dependencies"), data.get("optionalDependencies"))
    return {name for group in groups if isinstance(group, dict) for name in group}


def _first_line(lines: list[str], needle: str) -> int:
    return next((i for i, ln in enumerate(lines, 1) if needle in ln), 0)


def _node_cli(ctx: Context) -> list[Fact]:
    """A `bin` entry in a package.json is a command the package ships."""
    found = []
    for path in walk(ctx.repo, "package.json", 4):
        if package_json(path).get("bin"):
            rel = path.relative_to(ctx.repo).as_posix()
            n = _first_line(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), '"bin"'
            )  # lossy-ok: parse: the text is matched for a yes/no or one value, never stored or hashed
            found.append(Fact("cli", _where(rel, n) if n else rel))
    return found[:1]


def _node_dependencies(ctx: Context) -> list[Evidence]:
    found: list[Evidence] = []
    for path in walk(ctx.repo, "package.json", 4):
        have = _package_runtime_dependencies(package_json(path))
        rel = path.relative_to(ctx.repo).as_posix()
        lines = path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()  # lossy-ok: parse: the text is matched for a yes/no or one value, never stored or hashed
        for claim, names in _NODE_DEPENDENCY_EVIDENCE:
            if hit := sorted(h for h in have if any(fnmatch(h, n) for n in names)):
                n = _first_line(lines, f'"{hit[0]}"')
                found.append(Evidence(claim, _where(rel, n) if n else rel, "low"))
    return found


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
        lines = path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()  # lossy-ok: parse: the text is matched for a yes/no or one value, never stored or hashed
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
            lines = path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()  # lossy-ok: parse: the text is matched for a yes/no or one value, never stored or hashed
            for n, ln in enumerate(lines, 1):
                if ln.rstrip() == "volumes:" and n < len(lines) and lines[n].startswith((" ", "\t")) and lines[n].strip():
                    return [Evidence("stores-data", _where(path.relative_to(ctx.repo).as_posix(), n), "low")]
    return []


def detect_facts(ctx: Context) -> tuple[tuple[Fact, ...], tuple[Evidence, ...]]:
    """Every fact and piece of evidence the repo's files give, each once."""
    facts = [*_console_scripts(ctx), *_node_cli(ctx), *_sops(ctx)]
    evidence = [*_dependencies(ctx), *_node_dependencies(ctx), *_named_volumes(ctx)]
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
