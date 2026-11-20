"""One owner per fact: `owners.toml` names the file that holds each version pin; a second copy is a violation naming the owner."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blueprint.model import Context

TABLE = Path(__file__).resolve().parent / "owners.toml"
# A version spec that names one version: `==1.2.3`, `1.2.3`; a floor (`>=`) or range is not a copy of the pin.
_EXACT = re.compile(r"^(==\s*)?\d+(\.\d+)+\S*$")


@dataclass(frozen=True)
class Fact:
    name: str
    owner: str
    why: str
    copies: tuple[dict[str, object], ...]


def table() -> list[Fact]:
    rows = tomllib.loads(TABLE.read_text()).get("fact", [])
    return [Fact(str(r["name"]), str(r["owner"]), str(r.get("why", "")), tuple(r.get("copies", []))) for r in rows]


def _dig(data: dict[str, object], dotted: str) -> object:
    node: object = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _holds(ctx: Context, copy: dict[str, object]) -> bool:
    file = str(copy["file"])
    if "pattern" in copy:
        return any(re.search(str(copy["pattern"]), line) for line in (ctx.read(file) or "").splitlines())
    found = _dig(ctx.toml(file), str(copy["toml"]))
    if found is None:
        return False
    return not copy.get("exact") or bool(_EXACT.match(str(found).strip()))


def violations(ctx: Context, owner: str | None = None) -> list[str]:
    """One line per second copy of a fact, each naming the owner (`owner` limits the table to the facts that file owns)."""
    return [
        f"{fact.name} is also in {copy['file']}; the owner is {fact.owner} ({fact.why})"
        for fact in table()
        if owner in {None, fact.owner}
        for copy in fact.copies
        if _holds(ctx, copy)
    ]
