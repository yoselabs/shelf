"""Gate guards: owning domain checks and evidence."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from blueprint import gate_graph
from blueprint.concerns.gate_hooks import HOOK_CONFIG
from blueprint.model import (
    Context,
    Finding,
    FixedBy,
    failing,
    is_skipped,
    not_applicable,
    not_set_up,
    passing,
    walk,
)

if TYPE_CHECKING:
    from blueprint.gate_graph import Gate
# A script a recipe runs: `python3 x.py`, `uv run python x.py`, or `g=x.py` handed to python later.
# `python3 -I tools/x.py`: interpreter flags before the script (the recipes are run isolated) still name it.
_SCRIPT = re.compile(r"(?:python3?(?:\s+-\w+)*\s+|uv run python(?:\s+-\w+)*\s+|\b[A-Za-z_]\w*=)((?:[\w.-]+/)*[\w.-]+\.py)\b")


_HOOK_ENTRY = re.compile(r"^\s*(?:-\s*)?entry:\s*(.+?)\s*$", re.MULTILINE)
# Any `.py` path in a hook's entry (`uv run tools/x.py`, `python x.py`, a bare path); a glob such as `test_*.py` has no match.
_HOOK_SCRIPT = re.compile(r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+\.py)\b")


def _hook_entries(ctx: Context, recipes: str) -> list[str]:
    """The `entry:` lines of .pre-commit-config.yaml when the gate runs the hooks (`pre-commit run`, `prek run`).

    Why: a gate that runs pre-commit runs every hook's command, and the repo's own guards are usually among them.
    """
    if not gate_graph.HOOK_RUN.search(recipes):
        return []
    return _HOOK_ENTRY.findall(ctx.read(HOOK_CONFIG) or "")


def _gate_commands(ctx: Context, gate: Gate) -> str:
    """Everything the gate runs: its recipes (variables expanded) and the hook commands it triggers."""
    recipes = gate.gate_recipes()
    return "\n".join([recipes, *_hook_entries(ctx, recipes)])


def _gate_scripts(ctx: Context, gate: Gate) -> list[str]:
    found = [m for recipe in gate.reachable() for m in _SCRIPT.findall(recipe)]
    for entry in _hook_entries(ctx, gate.gate_recipes()):
        found += [m for m in _HOOK_SCRIPT.findall(entry) if not Path(m).name.startswith("test_")]
    return list(dict.fromkeys(m for m in found if ctx.path(m).is_file()))


def runs_blueprint(ctx: Context) -> Finding:
    """Gaps come back between audits unless the repo's own gate re-checks them on every commit."""
    gate = gate_graph.load(ctx)
    if gate is None:
        return not_applicable("no justfile: gate.one-command reports the missing gate")
    if "blueprint check" not in gate.gate_recipes():
        return not_set_up(
            "`just check` never runs blueprint",
            "copy the shelf's `blueprint` recipe into the justfile and add it to `check` (`just bootstrap` does both)",
            FixedBy.AUTO,
        )
    return passing("`just check` reaches `blueprint check --gate`")


def guards_have_red_tests(ctx: Context) -> Finding:
    """Each repo `*.py` that `just check` reaches, in a recipe or through its pre-commit hooks, is named by some test file.

    A guard never seen red is a hypothesis.
    """
    gate = gate_graph.load(ctx)
    if gate is None:
        return not_applicable("no justfile, so no guard scripts")
    scripts = _gate_scripts(ctx, gate)
    if not scripts:
        return not_applicable("`just check` runs no repo-local Python script")
    tests = [p.read_text(errors="replace") for p in walk(ctx.repo, "test_*.py")]
    # An unchanged copy of a blueprint recipe is tested where it is written, in the shelf; an edited copy is the repo's own.
    recipes = [s for s in scripts if _is_recipe_copy(ctx, s)]
    untested = [s for s in scripts if s not in recipes and not any(Path(s).stem in t or Path(s).stem.replace("-", "_") in t for t in tests)]
    if untested:
        return failing(
            f"no test names {', '.join(untested)}",
            # A gate script is a guard (it fails the gate on a violation) or a helper the gate calls (a queue, a generator).
            "add a test per script: for a guard, plant the violation it guards against and assert it fails; "
            "for a helper (a queue, a generator, a launcher), test the behaviour the gate relies on",
        )
    copied = f"; {', '.join(recipes)} unchanged from a blueprint recipe, tested in the shelf" if recipes else ""
    return passing(f"{len(scripts)} script(s) ({', '.join(scripts)}), each named by a test{copied}")


_RECIPES = Path(__file__).resolve().parent.parent / "recipes"


def _is_recipe_copy(ctx: Context, script: str) -> bool:
    shipped = _RECIPES / Path(script).name
    return shipped.is_file() and ctx.read(script) == shipped.read_text()


_CHECKER = re.compile(r"^(?:check|lint|validate|verify)[_-].+\.(?:py|sh)$")
_NOT_GUARDS = {"tests", "test"}


def _checker_scripts(ctx: Context) -> list[str]:
    """`check_*`, `lint_*`, `validate_*`, `verify_*` scripts (py, sh) under tools/ or scripts/, outside test folders and ignored paths."""
    found: list[str] = []
    for folder in ("tools", "scripts"):
        if not ctx.path(folder).is_dir():
            continue
        for path in walk(ctx.path(folder), "*"):
            rel = path.relative_to(ctx.repo).as_posix()
            if _CHECKER.match(path.name) and not _NOT_GUARDS & set(Path(rel).parts) and not is_skipped(rel, ctx.profile.ignore):
                found.append(rel)
    return sorted(found)


def checkers_wired(ctx: Context) -> Finding:
    """A checker nothing runs guards nothing: its name says check, and the repo's own docs may say run it before a commit."""
    gate = gate_graph.load(ctx)
    if gate is None:
        return not_applicable("no justfile: gate.one-command reports the missing gate")
    scripts = _checker_scripts(ctx)
    if not scripts:
        return not_applicable("no check_*/lint_* script under tools/ or scripts/")
    commands = _gate_commands(ctx, gate)
    unwired = [s for s in scripts if not re.search(rf"(?<![\w.-]){re.escape(Path(s).name)}", commands)]
    if unwired:
        return failing(
            f"`just check` never runs {', '.join(unwired)}",
            "run each from a recipe `just check` reaches (then gate.guards-have-red-tests wants a test per script), "
            "or delete it; a script kept on purpose is an override of gate.checkers-wired with a reason and an expiry or adr",
        )
    return passing(f"{len(scripts)} checker script(s), each run by the gate")
