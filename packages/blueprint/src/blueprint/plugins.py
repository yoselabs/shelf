"""Plugins: the unit a repo chooses (mission blueprint-plugins). A manifest per plugin names the rows it owns.

Step 1 only names ownership: nothing here changes which row is asked of a repo.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent / "plugins"
DEFAULTS = ("detected", "on", "off")


@dataclass(frozen=True)
class Plugin:
    """One plugin: `rows` are row ids or `*` globs; `default` says whether a repo is asked without choosing."""

    id: str
    title: str
    default: str
    requires: tuple[str, ...]
    rows: tuple[str, ...]

    def owns(self, row_id: str) -> bool:
        return any(fnmatchcase(row_id, pattern) for pattern in self.rows)


def load_plugins(directory: Path = PLUGIN_DIR) -> dict[str, Plugin]:
    """Every manifest in `directory`, by id."""
    found: dict[str, Plugin] = {}
    for path in sorted(directory.glob("*.toml")):
        data = tomllib.loads(path.read_text())
        plugin = Plugin(
            id=str(data["id"]),
            title=str(data["title"]),
            default=str(data["default"]),
            requires=tuple(data.get("requires", ())),
            rows=tuple(data["rows"]),
        )
        found[plugin.id] = plugin
    return found


def owners_of(row_id: str, plugins: dict[str, Plugin]) -> list[str]:
    """The ids of every plugin that claims the row: exactly one is healthy."""
    return [p.id for p in plugins.values() if p.owns(row_id)]


def plugin_of(row_id: str, plugins: dict[str, Plugin] | None = None) -> str:
    """The plugin that owns the row, or `?` when none or several claim it (the manifest test fails those)."""
    owners = owners_of(row_id, plugins if plugins is not None else load_plugins())
    return owners[0] if len(owners) == 1 else "?"
