"""Plugin manifests (mission blueprint-plugins, step 1): every row has exactly one owner and the requires graph is sound."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import TYPE_CHECKING

from blueprint import checkpoints
from blueprint.plugins import DEFAULTS, Plugin, load_plugins, owners_of, plugin_of, resolve
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo


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


def _rows_with(repo: Repo, toml: str | None, *, concern: str | None = None) -> tuple[set[str], tuple[str, ...], tuple[str, ...]]:
    repo.write("README.md", "x\n")
    repo.write(".beads/config.yaml", "no-git-ops: true\n")
    repo.write(".pre-commit-config.yaml", "repos: []\n")
    if toml is not None:
        repo.write("docs/blueprint/blueprint.toml", toml)
    repo.commit()
    result = run(repo.root, concern=concern, env=repo.env)
    return {r.id for r in result.rows}, result.notices, result.problems


def test_a_repo_without_a_plugins_table_is_asked_everything_it_was(repo: Repo) -> None:
    ids, notices, problems = _rows_with(repo, None)
    assert "backlog.tracker" in ids
    assert "hooks.beads-sync" in ids
    assert not [n for n in notices if n.startswith("plugin ")]
    assert not problems


def test_switching_beads_off_removes_every_beads_row_and_says_so(repo: Repo) -> None:
    ids, notices, _ = _rows_with(repo, "[plugins]\nbeads = false\n")
    assert not {i for i in ids if i.startswith("backlog.")}
    assert "hooks.beads-sync" not in ids
    assert "hooks.parses" in ids
    assert any(n.startswith("plugin `beads` is not asked: switched off") for n in notices)


def test_switching_git_hooks_off_switches_off_what_requires_it(repo: Repo) -> None:
    ids, notices, _ = _rows_with(repo, "[plugins]\ngit-hooks = false\n")
    assert not {i for i in ids if i.startswith(("hooks.", "backlog."))}
    assert any("plugin `beads` is not asked: requires git-hooks" in n for n in notices)
    assert any("plugin `gate` is not asked: requires git-hooks" in n for n in notices)


def test_an_unknown_plugin_or_a_non_boolean_switch_is_a_problem(repo: Repo) -> None:
    _, _, problems = _rows_with(repo, '[plugins]\nnope = false\nbeads = "no"\n')
    assert any("'nope' is not a plugin" in p for p in problems)
    assert any("beads must be true or false" in p for p in problems)


def test_an_off_by_default_plugin_is_asked_only_when_switched_on() -> None:
    plugins = {"x": Plugin("x", "X", "off", (), ("x.*",)), "y": Plugin("y", "Y", "on", ("x",), ("y.*",))}
    assert set(resolve((), plugins)) == {"x", "y"}
    assert "y" in resolve((), plugins)
    assert resolve((("x", True),), plugins) == {}
    assert set(resolve((("x", True), ("y", False)), plugins)) == {"y"}
