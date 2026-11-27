"""The gate as a graph of recipes, read from a justfile (the shelf's runner, ADR 0023).

A justfile is read through `just --dump --dump-format json`, so blueprint never parses just syntax itself:
recipes carry their dependencies (with arguments) and their body as fragments, with `{{var}}` left unexpanded.
A Makefile is not read (ADR 0023, ADR 0028: no backward compatibility); a repo with one and no justfile fails `gate.runner`.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from blueprint.model import Context

JUSTFILES = ("justfile", "Justfile", ".justfile")
MAKEFILE = "Makefile"

# A gate that runs the hook config (`pre-commit run --all-files`, `prek run`): every hook in it is part of the gate.
HOOK_RUN = re.compile(r"\b(?:pre-commit|prek)\s+run\b")
HOOK_CONFIG = ".pre-commit-config.yaml"
# `just container check`, `uv run just check`, `{{just_executable()}} test`: a body that runs another recipe.
_JUST_CALL = re.compile(r"\bjust\s+(?:--?[\w-]+(?:=\S+)?\s+)*([A-Za-z_][\w-]*)")


@dataclass(frozen=True)
class Recipe:
    """One recipe: the recipes it names (dependencies and arguments), and its body text."""

    names: tuple[str, ...]
    body: str


@dataclass(frozen=True)
class Gate:
    """The repo's gate: its justfile's path and text, and the recipes `check` can reach."""

    path: str
    text: str
    recipes: dict[str, Recipe] = field(default_factory=dict)
    # Why the graph is empty although the file exists: the runner is missing, or it rejected the file.
    unread: str = ""
    # The names handed to the `steps` recipe by `check`: the gate's steps, the ones any-gate can skip.
    stepped: tuple[str, ...] = ()

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
        run (coverage floor included) in `check-all`, which is run before a release tag.
        """
        return executable("\n".join(dict.fromkeys(self.reachable("check") + self.reachable("check-all"))))


_PRINTS = frozenset({"echo", "printf"})
_CHAIN = re.compile(r"&&|\|\||;|\|")


def executable(text: str) -> str:
    """`text` without the lines that only talk about a command: comments, and `echo`/`printf` (a name in a message runs nothing)."""
    kept = []
    for line in text.splitlines():
        words = line.lstrip(" \t@-").split(None, 1)
        if words and words[0].startswith("#"):
            continue
        if words and words[0] in _PRINTS:
            # what the message says runs nothing; a command chained after it (`echo "lint" && ruff check`) still does
            kept.append("".join(_CHAIN.split(line, maxsplit=1)[1:]))
            continue
        kept.append(line)
    return "\n".join(kept)


def just_command(ctx: Context) -> str:
    """`just` from PATH, else the repo's pinned one (`uv add --dev rust-just` puts it in .venv/bin)."""
    pinned = ctx.path(".venv/bin/just")
    return "just" if ctx.has("just") or not pinned.is_file() else str(pinned)


def load(ctx: Context) -> Gate | None:
    """The repo's gate: its justfile, or None.

    Read once per run: a dozen checkpoints ask, and each ask used to run `just --dump` again (measured on a2kay, 2026-11-27).
    """
    if "gate" not in ctx.memo:
        ctx.memo["gate"] = _read_gate(ctx)
    gate = ctx.memo["gate"]
    return gate if isinstance(gate, Gate) or gate is None else None


def _read_gate(ctx: Context) -> Gate | None:
    for name in JUSTFILES:
        if (text := ctx.read(name)) is not None:
            return _just(ctx, name, _with_imports(ctx, text))
    return None


_IMPORT = re.compile(r"^import\??\s+['\"]([^'\"]+)['\"]", re.MULTILINE)


def _with_imports(ctx: Context, text: str) -> str:
    """The justfile's text followed by the text of each file it imports (just flattens them: `.blueprint/*.just`, ADR 0029)."""
    return "\n".join([text, *(part for path in _IMPORT.findall(text) if (part := ctx.read(path)) is not None)])


def has_makefile_only(ctx: Context) -> bool:
    return not any(ctx.path(name).is_file() for name in JUSTFILES) and ctx.path(MAKEFILE).is_file()


# --- just ---------------------------------------------------------------------------------------------


def dump(ctx: Context, name: str) -> subprocess.CompletedProcess[str] | None:
    """`just --justfile <name> --dump --dump-format json`, run once per file per run (the graph and the shadowing check both ask)."""
    key = f"dump:{name}"
    if key not in ctx.memo:
        ctx.memo[key] = ctx.run(just_command(ctx), "--justfile", name, "--dump", "--dump-format", "json", timeout=60)
    cached = ctx.memo[key]
    return cached if isinstance(cached, subprocess.CompletedProcess) else None


def _just(ctx: Context, name: str, text: str) -> Gate:
    done = dump(ctx, name)
    if done is None:
        return Gate(name, text, unread="`just` is not installed or timed out")
    if done.returncode != 0:
        return Gate(name, text, unread=_last_line(done))
    try:
        graph = json.loads(done.stdout)
    except json.JSONDecodeError:
        return Gate(name, text, unread="`just --dump` printed no JSON")
    assignments = {n: a.get("value") for n, a in graph.get("assignments", {}).items()}
    known = set(graph["recipes"])
    recipes: dict[str, Recipe] = {}
    for recipe_name, recipe in graph["recipes"].items():
        body = "\n".join("".join(_fragment(part, assignments, 0) for part in line) for line in recipe["body"])
        names = [dep["recipe"] for dep in recipe["dependencies"]]
        # An argument that is a recipe's name is an edge: check -> steps("lint") reaches lint.
        names += [arg for dep in recipe["dependencies"] for arg in dep["arguments"] if isinstance(arg, str) and arg in known]
        names += [m for m in _JUST_CALL.findall(body) if m in known]
        recipes[recipe_name] = Recipe(tuple(dict.fromkeys(names)), body)
    stepped = tuple(
        dict.fromkeys(
            arg
            for dep in graph["recipes"].get("check", {}).get("dependencies", [])
            if dep["recipe"] == "steps"
            for arg in dep["arguments"]
            if isinstance(arg, str)
        )
    )
    return Gate(name, text, recipes, stepped=stepped)


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
