"""Gate command: owning domain checks and evidence."""

from __future__ import annotations

from blueprint import gate_graph
from blueprint.concerns.stacks.profile_data import StackProfile, load_profiles, profile_for
from blueprint.model import (
    Context,
    Finding,
    FixedBy,
    failing,
    not_applicable,
    not_checked,
    not_set_up,
    passing,
)


def _stack_profiles(ctx: Context) -> list[StackProfile]:
    """The profile of each detected stack, in detection order (a stack without one is left out)."""
    profiles = load_profiles()
    return [p for s in ctx.profile.stacks if (p := profile_for(s, profiles))]


def one_command(ctx: Context) -> Finding:
    """The justfile has a `check` recipe and `just --dry-run check` resolves."""
    onboard = next((p.onboard for p in _stack_profiles(ctx) if p.onboard), "")
    generic = "add a justfile whose `check` recipe runs every linter and the tests"
    if not ctx.profile.stacks:
        generic += (
            '; no code yet? declare the stack it will have, `[profile] stacks = ["python-uv"]` in '
            "docs/blueprint/blueprint.toml, for its own fix"
        )
    fixer = (onboard, FixedBy.AUTO) if onboard else (generic, FixedBy.AGENT)
    gate = gate_graph.load(ctx)
    if gate is None:
        return not_set_up("no justfile", *fixer)
    if not gate.has_recipe("check"):
        if gate.unread:
            return not_checked(
                f"the justfile cannot be read: {gate.unread} "
                "(pin the runner: `uv add --dev rust-just` with a pyproject.toml, else just in mise.toml)"
            )
        return not_set_up(f"the {gate.path} has no `check` recipe", *fixer)
    dry = ctx.run(gate_graph.just_command(ctx), *_DRY_RUN[1:], timeout=60)
    shown = " ".join(_DRY_RUN)
    if dry is None:
        return not_checked("`just` is not installed or timed out")
    if dry.returncode != 0:
        lines = (dry.stderr.strip() or dry.stdout.strip()).splitlines() or ["no output"]
        # just prints "error: <what>" first and a source excerpt after it.
        complaint = next((line for line in lines if line.startswith("error")), lines[-1])
        return failing(f"`{shown}` fails: {complaint}", "add or fix the recipe the gate names")
    return passing(f"`{shown}` resolves")


_DRY_RUN = ("just", "--dry-run", "check")
_PORT = "port each target to a recipe (same names; loops go in shebang recipes; no backticks)"


def _migration(ctx: Context) -> str:
    """Pin just where the repo already pins things: the pyproject's dev group for Python, mise.toml for every other stack."""
    runner = next(((p.runner_pin, p.runner_run) for p in _stack_profiles(ctx) if p.runner_pin), None)
    if runner:
        pin, run_it = runner
    else:
        pin, run_it = '`just = "<version>"` under [tools] in mise.toml, then `mise lock` (ADR 0024)', "run it as `just check`"
    return (
        f"move the Makefile to a justfile (ADR 0023; `blueprint init` writes the justfile parts, then edit the recipes): "
        f"pin just with {pin}, {_PORT}, {run_it}, delete the Makefile; the shelf's own justfile is the reference"
    )


def runner(ctx: Context) -> Finding:
    """One runner for every repo, so blueprint reads the gate graph from one JSON dump (ADR 0023)."""
    if gate_graph.has_makefile_only(ctx):
        return failing("the gate is a Makefile; the shelf's runner is just (a justfile)", _migration(ctx))
    if gate_graph.load(ctx) is None:
        return not_applicable("no gate: gate.one-command reports the missing one")
    return passing("a justfile holds the gate")
