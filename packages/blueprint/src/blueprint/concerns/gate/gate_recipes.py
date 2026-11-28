"""A consumer justfile that redefines a recipe blueprint renders must say so: a shadowed recipe is invisible to every other checkpoint."""

from __future__ import annotations

import json
import re
import shlex
from typing import TYPE_CHECKING

from blueprint import gate_graph, render
from blueprint.concerns.gate import gate_unreadable
from blueprint.model import Context, Finding, failing, not_applicable, not_checked, passing

if TYPE_CHECKING:
    from pathlib import Path

ID = "gate.recipe-shadowing"
FOLDER = ".blueprint"
# The extension point base.just declares for a repo to define; every other rendered name is blueprint's.
EXTENSION_POINTS = frozenset({"check-extra"})


def _dump_recipe_names(ctx: Context, path: str) -> set[str] | None:
    """Recipe names come from Just's parser, including defaulted parameters and imported definitions."""
    done = gate_graph.dump(ctx, path)
    if done is None or done.returncode != 0:
        return None
    return set(json.loads(done.stdout)["recipes"])


def shadowing(ctx: Context) -> Finding:
    """The justfile imports blueprint's rendered parts and defines a recipe of the same name."""
    own = next((n for n in gate_graph.JUSTFILES if ctx.path(n).is_file()), None)
    parts: list[Path] = sorted(ctx.path(FOLDER).glob("*.just")) if ctx.path(FOLDER).is_dir() else []
    if own is None or not parts:
        return not_applicable("the gate imports no blueprint-rendered parts")
    definitions = _dump_recipe_names(ctx, own)
    if definitions is None:
        return not_checked("just could not dump the repo's recipe definitions; fix the justfile or install its pinned just")
    owned: set[str] = set()
    for part in parts:
        baseline = _dump_recipe_names(ctx, part.relative_to(ctx.repo).as_posix())
        if baseline is None:
            return not_checked(f"just could not dump rendered recipe definitions in {part.name}")
        owned |= baseline
    # The dump flattens imports and loses source locations. Attribute its validated names to consumer declarations; do not interpret
    # parameter/default syntax. Assignments have a separate := token and indented lines belong to recipe bodies.
    consumer: set[str] = set()
    for line in render.own_recipe_text(ctx.repo).splitlines():
        if line and not line[0].isspace():
            words = line.split(maxsplit=1)
            if not (":=" in words[0] or (len(words) > 1 and words[1].startswith(":="))):
                consumer.add(words[0].removeprefix("@").split(":", 1)[0])
    clashes = sorted(consumer & definitions & owned - EXTENSION_POINTS)
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

# `uv run blueprint check ...`, `python3 -m blueprint gate test ...`, `blueprint check ...`: the words after the program name.
_CALL = re.compile(r"(?:\bblueprint|-m\s+blueprint)\s+((?:check|gate|init)\b[^\n;&|]*)")
# The engine run from a shelf clone: it moves with whatever is checked out there, so another session's commit breaks this gate.
_LIVE_CLONE = re.compile(r"PYTHONPATH=\S*packages/blueprint|\S*/shelf/packages/blueprint/src|--reference\s+\S*shelf")


def calls(ctx: Context) -> Finding:
    """A recipe runs `blueprint` with a flag it no longer has, or runs it from a shelf clone."""
    from blueprint.__main__ import known_flags  # noqa: PLC0415 -- __main__ imports every check, so it cannot be imported at load time

    if (blind := gate_unreadable.unreadable(ctx, "its calls of blueprint")) is not None:
        return blind
    gate = gate_graph.load(ctx)
    if gate is None or not gate.recipes:
        return not_applicable("no gate recipes to read")
    problems: list[str] = []
    for name, recipe in sorted(gate.recipes.items()):
        if _LIVE_CLONE.search(recipe.body):
            problems.append(f"{name} runs blueprint from a shelf clone (it changes with whatever is checked out there)")
        for call in _CALL.findall(recipe.body.replace("\\\n", " ")):
            words = shlex.split(call, comments=True)
            words = words[: words.index("--")] if "--" in words else words  # what follows `--` is the tool's own (pytest's)
            command, known = known_flags(words)
            problems += [
                f"{name} runs `blueprint {command}` with {flag}, which it does not have"
                for flag in sorted(
                    {
                        word.split("=", 1)[0]
                        for index, word in enumerate(words)
                        if word.startswith("--") and not (index and words[index - 1] == "--pytest-args")
                    }
                    - known
                    - {"--help"}
                )
            ]
    if problems:
        return failing(
            "; ".join(problems),
            "run the pinned engine, `uv run blueprint <command>` (blueprint is a dev dependency, pinned by the repo's lock), and use the "
            "flags `blueprint <command> --help` lists",
        )
    return passing("every recipe's blueprint call uses flags that exist, from the pinned engine")
