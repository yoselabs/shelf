"""The gate as a graph of recipes: read from a justfile (the shelf's runner, ADR 0023) or, for a repo not yet migrated, a Makefile.

A justfile is read through `just --dump --dump-format json`, so blueprint never parses just syntax itself:
recipes carry their dependencies (with arguments) and their body as fragments, with `{{var}}` left unexpanded.
A Makefile is read by the line-wise fallback below, kept so consumers still on make are judged rather than skipped.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import subprocess

    from blueprint.model import Context

JUSTFILES = ("justfile", "Justfile", ".justfile")
MAKEFILE = "Makefile"

_MAKE_TARGET = re.compile(r"^([A-Za-z][A-Za-z0-9_.-]*)\s*:(?!=)", re.MULTILINE)
_MAKE_VARIABLE = re.compile(r"^([A-Za-z_]\w*)\s*[:?]?=\s*(.*?)\s*$", re.MULTILINE)
_MAKE_VARIABLE_USE = re.compile(r"\$[({]([A-Za-z_]\w*)[)}]")
# `just container check-host`, `uv run just check`, `{{just_executable()}} test`: a body that runs another recipe.
_JUST_CALL = re.compile(r"\bjust\s+(?:--?[\w-]+(?:=\S+)?\s+)*([A-Za-z_][\w-]*)")


@dataclass(frozen=True)
class Recipe:
    """One recipe: the recipes it names (dependencies and arguments), and its body text."""

    names: tuple[str, ...]
    body: str


@dataclass(frozen=True)
class Gate:
    """The repo's gate: which runner owns it, its file's text, and the recipes `check` can reach."""

    runner: str  # "just" or "make"
    path: str
    text: str
    recipes: dict[str, Recipe] = field(default_factory=dict)
    # Why the graph is empty although the file exists: the runner is missing, or it rejected the file.
    unread: str = ""

    def has_recipe(self, name: str) -> bool:
        return name in self.recipes if self.recipes else bool(re.search(rf"^{re.escape(name)}\s*:(?!=)", self.text, re.MULTILINE))

    def reachable(self, start: str = "check") -> list[str]:
        """Bodies of every recipe `start` reaches, in name order; the whole file when the runner could not read it."""
        if not self.recipes:
            return [self.text]
        seen, queue = {start}, [start]
        while queue:
            for nxt in sorted(set(self.recipes.get(queue.pop(), Recipe((), "")).names) & self.recipes.keys() - seen):
                seen.add(nxt)
                queue.append(nxt)
        return [self.recipes[name].body for name in sorted(seen) if name in self.recipes]

    def gate_recipes(self) -> str:
        """The body text of everything `check` or `check-all` reaches, joined.

        `check-all` counts: a repo may narrow `check` to what a change touches and keep the whole
        run (coverage floor included) in `check-all`, which CI runs.
        """
        return "\n".join(dict.fromkeys(self.reachable("check") + self.reachable("check-all")))


def just_command(ctx: Context) -> str:
    """`just` from PATH, else the repo's pinned one (`uv add --dev rust-just` puts it in .venv/bin)."""
    pinned = ctx.path(".venv/bin/just")
    return "just" if ctx.has("just") or not pinned.is_file() else str(pinned)


def load(ctx: Context) -> Gate | None:
    """The repo's gate: its justfile when it has one (a Makefile beside it is leftover), else its Makefile, else None."""
    for name in JUSTFILES:
        if (text := ctx.read(name)) is not None:
            return _just(ctx, name, text)
    if (text := ctx.read(MAKEFILE)) is not None:
        return Gate("make", MAKEFILE, text, _make_recipes(text))
    return None


def has_makefile_only(ctx: Context) -> bool:
    return not any(ctx.path(name).is_file() for name in JUSTFILES) and ctx.path(MAKEFILE).is_file()


# --- just ---------------------------------------------------------------------------------------------


def _just(ctx: Context, name: str, text: str) -> Gate:
    done = ctx.run(just_command(ctx), "--justfile", name, "--dump", "--dump-format", "json", timeout=60)
    if done is None:
        return Gate("just", name, text, unread="`just` is not installed or timed out")
    if done.returncode != 0:
        return Gate("just", name, text, unread=_last_line(done))
    try:
        dump = json.loads(done.stdout)
    except json.JSONDecodeError:
        return Gate("just", name, text, unread="`just --dump` printed no JSON")
    assignments = {n: a.get("value") for n, a in dump.get("assignments", {}).items()}
    known = set(dump["recipes"])
    recipes: dict[str, Recipe] = {}
    for recipe_name, recipe in dump["recipes"].items():
        body = "\n".join("".join(_fragment(part, assignments, 0) for part in line) for line in recipe["body"])
        names = [dep["recipe"] for dep in recipe["dependencies"]]
        # An argument that is a recipe's name is an edge: check -> gate("check-host") reaches check-host.
        names += [arg for dep in recipe["dependencies"] for arg in dep["arguments"] if isinstance(arg, str) and arg in known]
        names += [m for m in _JUST_CALL.findall(body) if m in known]
        recipes[recipe_name] = Recipe(tuple(dict.fromkeys(names)), body)
    return Gate("just", name, text, recipes)


def _fragment(part: Any, assignments: dict[str, Any], depth: int) -> str:
    """A body line's piece: literal text, or a list of expressions interpolated from `{{ }}`."""
    if isinstance(part, str):
        return part
    return "".join(_expression(e, assignments, depth) for e in part)


def _expression(expr: Any, assignments: dict[str, Any], depth: int) -> str:
    if isinstance(expr, str):
        return expr
    kind, *rest = expr
    if kind == "variable":
        value = assignments.get(rest[0])
        # A recipe parameter is not an assignment: it stays `{{name}}`. Depth guards a self-referencing assignment.
        return _expression(value, assignments, depth + 1) if value is not None and depth < 8 else "{{" + str(rest[0]) + "}}"
    if kind == "call":
        return "just" if rest[0] == "just_executable" else "{{" + str(rest[0]) + "()}}"
    if kind == "concatenate":
        return "".join(_expression(e, assignments, depth) for e in rest)
    return "{{" + str(kind) + "}}"


def _last_line(done: subprocess.CompletedProcess[str]) -> str:
    lines = [line.strip() for line in (done.stderr or done.stdout).splitlines() if line.strip()]
    return next((line for line in lines if line.startswith("error")), lines[-1] if lines else "no output")


# --- make (fallback) ----------------------------------------------------------------------------------


def _make_recipes(makefile: str) -> dict[str, Recipe]:
    variables = dict(_MAKE_VARIABLE.findall(makefile))
    matches = list(_MAKE_TARGET.finditer(makefile))
    raw: dict[str, tuple[list[str], str]] = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(makefile)
        header, _, body = makefile[m.start() : end].partition("\n")
        recipe = "\n".join(line for line in body.splitlines() if line.startswith("\t"))
        raw[m.group(1)] = (header.split(":", 1)[1].split(), recipe)
    recipes: dict[str, Recipe] = {}
    for name, (prereqs, recipe) in raw.items():
        # A recipe that names another target runs it (`$(MAKE) x`, `make x`): an edge, like a prerequisite.
        words = set(prereqs) | set(re.findall(r"[\w.-]+", recipe))
        recipes[name] = Recipe(tuple(sorted(words & raw.keys() - {name})), _expand(recipe, variables))
    return recipes


def _expand(text: str, variables: dict[str, str]) -> str:
    """`$(PY)` and `${PY}` replaced by the Makefile's simple `PY := value` lines (three passes, for nested names).

    Why: a recipe written `$(PY) tools/check_design.py` hides its script from every pattern that reads recipes.
    """
    for _ in range(3):
        text = _MAKE_VARIABLE_USE.sub(lambda m: variables.get(m.group(1), m.group(0)), text)
    return text
