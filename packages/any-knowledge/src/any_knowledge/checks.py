"""The knowledge checks: the glossary, living ADRs with frontmatter, and the generated decision index. Each is a list of problems."""

from __future__ import annotations

from typing import TYPE_CHECKING

from any_knowledge import adr

if TYPE_CHECKING:
    from pathlib import Path

INDEX_PATH = f"{adr.FOLDER}/{adr.INDEX}"
REGENERATE = "python -m any_knowledge index --write"
FORMAT = (
    "frontmatter: id (the file's NNNN), title, statement (one line, the decision), concerns [list], "
    f"status ({'/'.join(adr.STATUSES)}), decided_by, updated (YYYY-MM-DD); body: decision on top, `## History` below"
)


def glossary(repo: Path) -> list[str]:
    """CONTEXT.md (or CONTEXT-MAP.md) at the root, when the repo keeps one at all: none is a problem only for a repo that asks."""
    if (repo / "CONTEXT.md").is_file() or (repo / "CONTEXT-MAP.md").is_file():
        return []
    return ["no CONTEXT.md"]


def adr_format(repo: Path) -> list[str]:
    """One line per malformed ADR; none when there are no ADRs (a repo without docs/adr/ runs nothing)."""
    return [f"{p.name}: {'; '.join(issues)}" for p in adr.files(repo) if (issues := adr.problems(p))]


def adr_index(repo: Path) -> list[str]:
    """The index is missing or differs from what the ADRs generate; none when there are no ADRs."""
    if not adr.files(repo):
        return []
    path = repo / INDEX_PATH
    if not path.is_file():
        return [f"no {INDEX_PATH}"]
    if path.read_text(encoding="utf-8") != adr.index(repo):
        return [f"{INDEX_PATH} differs from what the ADRs generate"]
    return []
