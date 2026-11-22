"""One direction (mission blueprint-plugins): a concern module imports another plugin's concern module only through a declared `requires`.

Each `packages/blueprint/src/blueprint/plugins/*.toml` names the `concerns/*.py` modules its plugin owns. A module of plugin P importing a
module of plugin Q is allowed when Q is in P's `requires` closure (or both are P). Nothing else is: a plugin that needs another says so in
its manifest, which also switches it off with the other. No rows: a hit is fixed by declaring the requirement or moving the code.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

from any_arch import Hit, Rule, Source, check, plant
from blueprint.plugins import PLUGIN_DIR, load_plugins, requires_closure

_ROOT = Path(__file__).resolve().parent.parent
_PLUGINS = load_plugins(PLUGIN_DIR)
_HOME = {module: plugin.id for plugin in _PLUGINS.values() for module in plugin.modules}
_CONCERNS = "blueprint.concerns"
_CONCERNS_DIR = Path("packages/blueprint/src/blueprint/concerns")


def _resolve(dotted: str) -> Iterator[str]:
    """The longest known module a dotted path names (`beads.backlog.STRICT` reaches `beads.backlog`)."""
    parts = dotted.split(".")
    for end in range(len(parts), 0, -1):
        if ".".join(parts[:end]) in _HOME:
            yield ".".join(parts[:end])
            return
    yield parts[0]


def _imported_modules(node: ast.AST) -> Iterator[str]:
    """The `concerns` module names an import statement reaches."""
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        if node.module == _CONCERNS or node.module.startswith(f"{_CONCERNS}."):
            base = node.module.removeprefix(_CONCERNS).removeprefix(".")
            for alias in node.names:
                yield from _resolve(f"{base}.{alias.name}" if base else alias.name)
    elif isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name.startswith(f"{_CONCERNS}."):
                yield from _resolve(alias.name.removeprefix(f"{_CONCERNS}."))


def _module_of(rel: str) -> str:
    """`beads.backlog` for packages/blueprint/src/blueprint/concerns/beads/backlog.py; `hooks` for concerns/git_hooks/hooks.py."""
    return ".".join(Path(rel).relative_to(_CONCERNS_DIR).with_suffix("").parts)


def _undeclared(source: Source) -> Iterator[Hit]:
    """`module->module` for an import across plugins that the importer's plugin does not require."""
    name = _module_of(source.rel)
    mine = _HOME.get(name)
    if mine is None:
        return
    for node in ast.walk(source.tree):
        for target in _imported_modules(node):
            theirs = _HOME.get(target)
            if theirs is not None and theirs != mine and theirs not in requires_closure(mine, _PLUGINS):
                yield f"{name}->{target}", node.lineno


_RULE = Rule(
    name="plugin imports",
    fix="a concern module imports another plugin's module only if its plugin `requires` that plugin (plugins/<id>.toml); "
    "add the requirement, or move the shared code into a plugin both require (`stacks`)",
    find=_undeclared,
    rows={},
    scope=("packages/blueprint/src/blueprint/concerns/**/*.py",),
)


def test_a_plugin_imports_another_only_through_requires() -> None:
    check(_RULE, _ROOT)


def test_every_concern_module_has_exactly_one_home_plugin() -> None:
    base = _ROOT / _CONCERNS_DIR
    modules = {".".join(p.relative_to(base).with_suffix("").parts) for p in base.rglob("*.py") if p.name != "__init__.py"}
    owned = [m for plugin in _PLUGINS.values() for m in plugin.modules]
    assert sorted(modules - set(owned)) == [], "a concerns module no plugin lists in `modules`"
    assert sorted({m for m in owned if owned.count(m) > 1}) == [], "a concerns module two plugins list"
    assert sorted(set(owned) - modules) == [], "a plugin lists a module that does not exist"


def test_the_rule_sees_a_planted_undeclared_import(tmp_path: Path) -> None:
    found = plant(
        _RULE, tmp_path, "from blueprint.concerns.beads import backlog\n", path="packages/blueprint/src/blueprint/concerns/agents/agents.py"
    )
    assert list(found) == ["agents.agents->beads.backlog"]
