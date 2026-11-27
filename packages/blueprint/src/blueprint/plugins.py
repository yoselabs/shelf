"""Plugins: the unit a repo chooses (mission blueprint-plugins). A manifest per plugin names the rows it owns.

A repo's `[plugins]` table in blueprint.toml switches a plugin on or off; `resolve` turns the switches, the defaults and `requires`
into the set of plugins asked, with the reason each other one is not.
"""

from __future__ import annotations

import functools
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
    # The `concerns/<plugin>/*.py` modules this plugin owns, as dotted paths below `blueprint.concerns` (`git_hooks.hooks`).
    modules: tuple[str, ...] = ()

    def owns(self, row_id: str) -> bool:
        return any(fnmatchcase(row_id, pattern) for pattern in self.rows)


def load_plugins(directory: Path = PLUGIN_DIR) -> dict[str, Plugin]:
    """Every manifest in `directory`, by id. The shipped folder is parsed once per process (it cannot change under a run);
    any other is read on each call."""
    return dict(_shipped()) if directory == PLUGIN_DIR else _parse(directory)


@functools.cache
def _shipped() -> dict[str, Plugin]:
    return _parse(PLUGIN_DIR)


def _parse(directory: Path) -> dict[str, Plugin]:
    found: dict[str, Plugin] = {}
    for path in sorted(directory.glob("*.toml")):
        data = tomllib.loads(path.read_text())
        plugin = Plugin(
            id=str(data["id"]),
            title=str(data["title"]),
            default=str(data["default"]),
            requires=tuple(data.get("requires", ())),
            rows=tuple(data["rows"]),
            modules=tuple(data.get("modules", ())),
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


def resolve(switches: tuple[tuple[str, bool], ...], plugins: dict[str, Plugin] | None = None) -> dict[str, str]:
    """The plugins NOT asked of a repo, each with why. A plugin missing from the result is asked.

    `on` and `detected` plugins are asked unless the repo switches them off (a `detected` plugin's own rows still apply only where
    their detection fires); an `off` plugin is asked only when switched on; a plugin whose required plugin is not asked is not
    asked either.
    """
    plugins = plugins if plugins is not None else load_plugins()
    chosen = dict(switches)
    reasons: dict[str, str] = {}
    for plugin in plugins.values():
        if chosen.get(plugin.id) is False:
            reasons[plugin.id] = "switched off in docs/blueprint/blueprint.toml"
        elif plugin.default == "off" and chosen.get(plugin.id) is not True:
            reasons[plugin.id] = "off by default; switch it on in docs/blueprint/blueprint.toml"
    changed = True
    while changed:
        changed = False
        for plugin in plugins.values():
            if plugin.id in reasons:
                continue
            blocked = next((dep for dep in plugin.requires if dep in reasons), None)
            if blocked is not None:
                reasons[plugin.id] = f"requires {blocked}, which is not asked ({reasons[blocked]})"
                changed = True
    return reasons


def notices_for(reasons: dict[str, str], plugins: dict[str, Plugin] | None = None) -> tuple[str, ...]:
    """One line per plugin not asked: never silent."""
    plugins = plugins if plugins is not None else load_plugins()
    return tuple(f"plugin `{pid}` is not asked: {why}" for pid, why in reasons.items() if pid in plugins)


def requires_closure(plugin_id: str, plugins: dict[str, Plugin]) -> set[str]:
    """Every plugin `plugin_id` requires, directly or through another."""
    seen: set[str] = set()
    stack = list(plugins[plugin_id].requires)
    while stack:
        dep = stack.pop()
        if dep not in seen:
            seen.add(dep)
            stack.extend(plugins[dep].requires)
    return seen
