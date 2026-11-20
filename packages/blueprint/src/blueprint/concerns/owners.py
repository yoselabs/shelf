"""`stack.one-owner`: each version pin lives in one file (owners.toml); a second copy fails and names the owner."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint import owners
from blueprint.model import check, failing, passing

if TYPE_CHECKING:
    from blueprint.model import Context, Finding


@check("stack.one-owner", "every pinned fact (Python, .NET SDK, uv) is held by its one owner file, never copied", layer="stack")
def one_owner(ctx: Context) -> Finding:
    """Judge the repo's files against the fact-to-owner table; no network."""
    found = owners.violations(ctx)
    if found:
        return failing("; ".join(found), "delete the copy; the owner file is the only place the fact is written")
    return passing(f"{len(owners.table())} facts, each in its one owner file")
