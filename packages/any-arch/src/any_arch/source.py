"""One parse per file per run: the parsed tree of every file a rule scans is cached for the life of the process."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class Source:
    """One parsed file. `rel` is the repo-relative posix path; `package` is the `packages/<name>` folder, or "" outside `packages/`."""

    rel: str
    package: str
    text: str
    tree: ast.Module  # shared by every rule: read it, never change it


@cache
def _parse(path: Path, mtime_ns: int, size: int) -> tuple[str, ast.Module]:
    del mtime_ns, size  # cache keys only: an edited file is parsed again, an untouched one never
    text = path.read_text(encoding="utf-8")
    return text, ast.parse(text)


def sources(root: Path, scope: tuple[str, ...]) -> list[Source]:
    """Every file under `root` matching a glob in `scope`, sorted by path, parsed once per run."""
    paths = sorted({path for pattern in scope for path in root.glob(pattern) if path.is_file()})
    found: list[Source] = []
    for path in paths:
        stat = path.stat()
        text, tree = _parse(path, stat.st_mtime_ns, stat.st_size)
        rel = path.relative_to(root)
        found.append(Source(rel.as_posix(), rel.parts[1] if rel.parts[0] == "packages" else "", text, tree))
    return found
