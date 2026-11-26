"""One snapshot, one spelling: a consumer's shelf git sources share one tag and one URL; no override re-pins a shelf package.

The rule is `shelf_sources.toml`. Why: a package whose siblings are `workspace = true` resolves them at its parent's own
URL and tag, so mixed tags or spellings make `uv lock` fail with conflicting URLs (ogy kept four overrides over it).
"""

from __future__ import annotations

import re
import tomllib
from importlib import metadata
from pathlib import Path

from blueprint.names import canonical_name

TABLE = Path(__file__).resolve().parent / "shelf_sources.toml"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")
_SHELF = "yoselabs/shelf"


def canonical_url() -> str:
    return str(tomllib.loads(TABLE.read_text())["url"])


def snapshot_tag() -> str:
    """The one tag to use: the rule's template filled with the installed blueprint's version."""
    return str(tomllib.loads(TABLE.read_text())["tag"]).format(version=metadata.version("blueprint"))


def sources(pyproject: dict[str, object]) -> dict[str, dict[str, object]]:
    """The `[tool.uv.sources]` entries whose git URL points at the shelf."""
    tool = pyproject.get("tool")
    uv = tool.get("uv") if isinstance(tool, dict) else None
    found = uv.get("sources") if isinstance(uv, dict) else None
    if not isinstance(found, dict):
        return {}
    return {n: s for n, s in found.items() if isinstance(s, dict) and _SHELF in str(s.get("git", ""))}


def _overrides(pyproject: dict[str, object]) -> list[str]:
    tool = pyproject.get("tool")
    uv = tool.get("uv") if isinstance(tool, dict) else None
    found = uv.get("override-dependencies") if isinstance(uv, dict) else None
    return [str(x) for x in found] if isinstance(found, list) else []


def problems(pyproject: dict[str, object]) -> list[str]:
    """One line per way the shelf sources disagree, or an override re-pins a shelf package."""
    shelf = sources(pyproject)
    out: list[str] = []
    wrong_url = sorted(n for n, s in shelf.items() if str(s["git"]) != canonical_url())
    if wrong_url:
        out.append(f"{', '.join(wrong_url)}: URL is not {canonical_url()} (no `.git`, no trailing slash)")
    tags = {str(s.get("tag", "<none>")) for s in shelf.values()}
    if len(tags) > 1:
        out.append(f"the shelf sources sit at {len(tags)} tags ({', '.join(sorted(tags))}); use {snapshot_tag()} for all")
    elif tags == {"<none>"}:
        out.append(f"the shelf sources have no tag; use {snapshot_tag()} for all")
    for line in _overrides(pyproject):
        match = _NAME.match(line.strip())
        if match and canonical_name(match.group()) in {canonical_name(n) for n in shelf}:
            out.append(f"override-dependencies re-pins the shelf package {match.group()}: delete it, one snapshot tag needs none")
    return out


_URL = re.compile(r'(git\s*=\s*)"[^"]*yoselabs/shelf[^"]*"')
_TAG = re.compile(r'(tag\s*=\s*)"[^"]*"')


def normalize(text: str) -> str:
    """`pyproject.toml` text with every shelf source line at the canonical URL and the snapshot tag (other lines untouched)."""
    lines = []
    for line in text.splitlines(keepends=True):
        if _URL.search(line):
            fixed = _URL.sub(lambda m: f'{m.group(1)}"{canonical_url()}"', line)
            lines.append(_TAG.sub(lambda m: f'{m.group(1)}"{snapshot_tag()}"', fixed))
        else:
            lines.append(line)
    return "".join(lines)
