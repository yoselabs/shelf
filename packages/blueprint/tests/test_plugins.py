"""Plugin manifests (mission blueprint-plugins, step 1): every row has exactly one owner and the requires graph is sound."""

from __future__ import annotations

from fnmatch import fnmatchcase

from blueprint import checkpoints
from blueprint.plugins import DEFAULTS, load_plugins, owners_of, plugin_of


def test_every_listed_row_has_exactly_one_plugin() -> None:
    plugins = load_plugins()
    bad = {row.id: owners_of(row.id, plugins) for row in checkpoints.listing() if len(owners_of(row.id, plugins)) != 1}
    assert not bad, f"rows with no plugin or several: {bad}"


def test_every_manifest_pattern_owns_something() -> None:
    plugins = load_plugins()
    ids = [row.id for row in checkpoints.listing()]
    dead = [(p.id, pattern) for p in plugins.values() for pattern in p.rows if not any(owners_of_pattern(pattern, i) for i in ids)]
    assert not dead, f"manifest rows that match no checkpoint: {dead}"


def owners_of_pattern(pattern: str, row_id: str) -> bool:
    return fnmatchcase(row_id, pattern)


def test_defaults_are_known_and_requires_name_real_plugins_without_a_cycle() -> None:
    plugins = load_plugins()
    for plugin in plugins.values():
        assert plugin.default in DEFAULTS, plugin.id
        assert set(plugin.requires) <= set(plugins), (plugin.id, plugin.requires)

    for plugin in plugins.values():
        stack, seen = list(plugin.requires), set()
        while stack:
            dep = stack.pop()
            assert dep != plugin.id, f"{plugin.id} requires itself through a cycle"
            if dep not in seen:
                seen.add(dep)
                stack.extend(plugins[dep].requires)


def test_the_listing_names_each_rows_plugin() -> None:
    row = next(r for r in checkpoints.listing("backlog.lint"))
    assert row.plugin == "beads"
    assert plugin_of("hooks.beads-sync") == "beads"
    assert plugin_of("hooks.parses") == "git-hooks"
