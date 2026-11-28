"""`stack.shelf-sources`: a consumer's shelf git sources share one tag and one URL spelling, and no override re-pins one."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint import shelf_sources
from blueprint.model import check, failing, not_applicable, passing

if TYPE_CHECKING:
    from blueprint.model import Context, Finding


@check(
    "stack.shelf-sources",
    "every shelf git source in [tool.uv.sources] shares one tag and one URL spelling, and override-dependencies re-pins no shelf package",
    layer="stack",
)
def shelf_sources_agree(ctx: Context) -> Finding:
    """Judge pyproject.toml against shelf_sources.toml; no network. New checkpoints warn first (ADR 0018)."""
    pyproject = ctx.toml(ctx.py("pyproject.toml"))
    shelf = shelf_sources.sources(pyproject)
    if not shelf:
        return not_applicable("no shelf git source in pyproject.toml")
    found = shelf_sources.problems(pyproject)
    if found:
        remedy = f"write every shelf source at {shelf_sources.snapshot_tag()} with the one URL (`blueprint init` does), drop the overrides"
        return failing("; ".join(found), remedy)
    return passing(f"{len(shelf)} shelf sources at one tag and one spelling")
