"""Boundary fitness: a shelf package must not import any consumer app.

The shelf sits BELOW its consumers. If a package here imports ``a2kay`` / ``a2web`` / …, the
dependency arrow has flipped and the package is no longer reusable. This is the inverted form of
a2kay's ``test_no_a2kay_dependency`` — here the shelf forbids ALL known consumers, not just one host.

Pure ``ast``, zero third-party dependencies, so it runs even before ``uv sync``.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

#: Top-level modules that are CONSUMERS of the shelf. A shelf package importing any of these has
#: inverted the dependency arrow. Extend as new consumer apps appear.
FORBIDDEN_CONSUMERS: frozenset[str] = frozenset({"a2kay", "a2web", "a2kit", "a2db", "a2effect", "a2atlassian"})


def imported_top_levels(py: Path) -> set[str]:
    """Return the set of top-level module names imported by a single .py file."""
    tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
    seen: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                seen.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            seen.add(node.module.split(".")[0])
    return seen


def assert_no_consumer_imports(
    package_src: Path,
    forbidden: frozenset[str] = FORBIDDEN_CONSUMERS,
) -> None:
    """Raise AssertionError if any .py under ``package_src`` imports a forbidden consumer app."""
    offenders: list[str] = []
    for py in sorted(package_src.rglob("*.py")):
        bad = imported_top_levels(py) & forbidden
        if bad:
            offenders.append(f"{py}: imports {sorted(bad)}")
    if offenders:
        raise AssertionError("shelf package imports a consumer app (dependency arrow inverted):\n" + "\n".join(offenders))
