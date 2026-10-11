"""Knowledge: the repo's glossary and its decisions, kept where agents find them and short enough to load."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint import adr
from blueprint.model import FixedBy, check, failing, not_set_up, passing

if TYPE_CHECKING:
    from blueprint.model import Context, Finding

_INDEX = f"{adr.FOLDER}/{adr.INDEX}"
_REGENERATE = "PYTHONPATH=<shelf>/packages/blueprint/src python3 -m blueprint adr-index --repo . --write"
# A recipe named in evidence, so the agent fixing it does not need the skill open.
_FORMAT = (
    "frontmatter: id (the file's NNNN), title, statement (one line, the decision), concerns [list], "
    f"status ({'/'.join(adr.STATUSES)}), decided_by, updated (YYYY-MM-DD); body: decision on top, `## History` below"
)


@check("knowledge.glossary", "CONTEXT.md at the root names the domain's concepts (or CONTEXT-MAP.md points to several)")
def glossary(ctx: Context) -> Finding:
    """One glossary agents and code share; the domain-modeling skill writes it."""
    for name in ("CONTEXT.md", "CONTEXT-MAP.md"):
        if ctx.read(name) is not None:
            return passing(f"{name} present")
    return not_set_up("no CONTEXT.md", "write CONTEXT.md: one entry per domain term, a one-line definition and _Avoid_ names")


@check("knowledge.adr-format", f"every decision is a living ADR in {adr.FOLDER}/NNNN-slug.md with complete frontmatter")
def adr_format(ctx: Context) -> Finding:
    """Frontmatter is what the index is built from; a file without it is a decision agents never see."""
    found = adr.files(ctx.repo)
    if not found:
        return not_set_up(f"no ADRs in {adr.FOLDER}/", f"record the repo's key decisions as {adr.FOLDER}/0001-slug.md; {_FORMAT}")
    bad = [f"{p.name} ({'; '.join(issues)})" for p in found if (issues := adr.problems(p))]
    if bad:
        shown = ", ".join(bad[:5]) + (f", and {len(bad) - 5} more" if len(bad) > 5 else "")
        return failing(f"{len(bad)} of {len(found)} ADRs malformed: {shown}", f"rewrite each to the format: {_FORMAT}")
    return passing(f"{len(found)} ADRs, frontmatter complete")


@check("knowledge.adr-index", f"{_INDEX} is generated from the ADRs and current")
def adr_index(ctx: Context) -> Finding:
    """Agents read the index, never every ADR; a stale index tells them an old decision."""
    if not adr.files(ctx.repo):
        return not_set_up(f"no ADRs, so no {_INDEX}", f"record ADRs, then {_REGENERATE}")
    current = ctx.read(_INDEX)
    if current is None:
        return not_set_up(f"no {_INDEX}", _REGENERATE, FixedBy.AUTO)
    if current != adr.index(ctx.repo):
        return failing(f"{_INDEX} differs from what the ADRs generate", _REGENERATE, FixedBy.AUTO)
    return passing(f"{_INDEX} current")
