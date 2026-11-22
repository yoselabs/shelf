"""A consumer justfile that redefines a recipe blueprint renders must say so: a shadowed recipe is invisible to every other checkpoint."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from blueprint import gate_graph
from blueprint.model import Context, Finding, failing, not_applicable, passing

if TYPE_CHECKING:
    from pathlib import Path

ID = "gate.recipe-shadowing"
FOLDER = ".blueprint"
# The extension point base.just declares for a repo to define; every other rendered name is blueprint's.
EXTENSION_POINTS = frozenset({"check-extra"})
_RECIPE = re.compile(r"^@?([A-Za-z_][\w-]*)(?:[ \t]+[^:=\n]*)?:(?!=)", re.MULTILINE)


def recipe_names(text: str) -> set[str]:
    """The names of the recipes `text` defines (a line at column 0 that is `name [params]:`, never an assignment)."""
    return set(_RECIPE.findall(text))


def shadowing(ctx: Context) -> Finding:
    """The justfile imports blueprint's rendered parts and defines a recipe of the same name."""
    own = next((t for n in gate_graph.JUSTFILES if (t := ctx.read(n)) is not None), None)
    parts: list[Path] = sorted(ctx.path(FOLDER).glob("*.just")) if ctx.path(FOLDER).is_dir() else []
    if own is None or not parts:
        return not_applicable("the gate imports no blueprint-rendered parts")
    owned: set[str] = set()
    for part in parts:
        owned |= recipe_names(part.read_text(encoding="utf-8"))
    clashes = sorted(recipe_names(own) & owned - EXTENSION_POINTS)
    excused = {name: o for name in clashes if (o := ctx.excused(ID, name)) is not None}
    open_ = [name for name in clashes if name not in excused]
    if open_:
        return failing(
            f"the justfile redefines blueprint's recipe{'s' if len(open_) > 1 else ''} {', '.join(open_)}: no checkpoint sees what the "
            "replacement runs, so the gate's guarantee for that step is unchecked",
            f'delete the repo\'s recipe and use blueprint\'s, or declare why it differs: an [[override]] id = "{ID}" scope = "<recipe>" '
            "with a reason and an end date or an ADR, in docs/blueprint/blueprint.toml. A missing capability is a blueprint gap: file it",
        )
    if excused:
        return passing(f"{len(excused)} redefined recipe(s) declared by override: {', '.join(excused)}")
    return passing(f"the justfile redefines none of blueprint's {len(owned)} recipes")


# --- gate.recipe-calls: what a recipe runs of blueprint must exist, and come from the pinned engine ----------------------------

CALLS_ID = "gate.recipe-calls"
# `uv run blueprint check ...`, `python3 -m blueprint gate test ...`, `blueprint check ...`: the words after the program name.
_CALL = re.compile(r"(?:\bblueprint|-m\s+blueprint)\s+((?:check|gate|init)\b[^\n;&|]*)")
# The engine run from a shelf clone: it moves with whatever is checked out there, so another session's commit breaks this gate.
_LIVE_CLONE = re.compile(r"PYTHONPATH=\S*packages/blueprint|\S*/shelf/packages/blueprint/src|--reference\s+\S*shelf")


def calls(ctx: Context) -> Finding:
    """A recipe runs `blueprint` with a flag it no longer has, or runs it from a shelf clone."""
    from blueprint.__main__ import known_flags  # noqa: PLC0415 -- __main__ imports every check, so it cannot be imported at load time

    gate = gate_graph.load(ctx)
    if gate is None or not gate.recipes:
        return not_applicable("no gate recipes to read")
    problems: list[str] = []
    for name, recipe in sorted(gate.recipes.items()):
        if _LIVE_CLONE.search(recipe.body):
            problems.append(f"{name} runs blueprint from a shelf clone (it changes with whatever is checked out there)")
        for call in _CALL.findall(recipe.body):
            words = call.split("#", 1)[0].split()
            command, known = known_flags(words)
            problems += [
                f"{name} runs `blueprint {command}` with {flag}, which it does not have"
                for flag in sorted({w.split("=", 1)[0] for w in words if w.startswith("--")} - known - {"--help"})
            ]
    if problems:
        return failing(
            "; ".join(problems),
            "run the pinned engine, `uv run blueprint <command>` (blueprint is a dev dependency, pinned by the repo's lock), and use the "
            "flags `blueprint <command> --help` lists",
        )
    return passing("every recipe's blueprint call uses flags that exist, from the pinned engine")
