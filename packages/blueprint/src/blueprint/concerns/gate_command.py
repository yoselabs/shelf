"""Gate command: owning domain checks and evidence."""

from __future__ import annotations

from blueprint import gate_graph
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

_ONBOARD = (
    "the shelf onboarding writes the gate: `just bootstrap`, or python3 <shelf>/.agents/skills/onboard-consumer/scripts/onboard.py --repo ."
)


def one_command(ctx: Context) -> Finding:
    """The justfile has a `check` recipe and `just --dry-run check` resolves (a Makefile: `make -n check`)."""
    python = any(s.startswith("python") for s in ctx.profile.stacks)
    generic = "add a justfile whose `check` recipe runs every linter and the tests"
    if not ctx.profile.stacks:
        generic += (
            '; no code yet? declare the stack it will have, `[profile] stacks = ["python-uv"]` in '
            "docs/blueprint/blueprint.toml, for its own fix"
        )
    fixer = (_ONBOARD, FixedBy.AUTO) if python else (generic, FixedBy.AGENT)
    gate = gate_graph.load(ctx)
    if gate is None:
        return not_set_up("no justfile", *fixer)
    if not gate.has_recipe("check"):
        if gate.unread and gate.runner == "just":
            return not_checked(
                f"the justfile cannot be read: {gate.unread} "
                "(pin the runner: `uv add --dev rust-just` with a pyproject.toml, else just in mise.toml)"
            )
        return not_set_up(f"the {gate.path} has no `check` {'recipe' if gate.runner == 'just' else 'target'}", *fixer)
    argv = _DRY_RUN[gate.runner]
    dry = ctx.run(gate_graph.just_command(ctx) if gate.runner == "just" else argv[0], *argv[1:], timeout=60)
    shown = " ".join(argv)
    if dry is None:
        return not_checked(f"`{gate.runner}` is not installed or timed out")
    if dry.returncode != 0:
        lines = (dry.stderr.strip() or dry.stdout.strip()).splitlines() or ["no output"]
        # just prints "error: <what>" first and a source excerpt after it; make's last line is the error.
        complaint = next((line for line in lines if line.startswith("error")), lines[-1])
        return failing(f"`{shown}` fails: {complaint}", "add or fix the recipe the gate names")
    return passing(f"`{shown}` resolves")


_DRY_RUN = {"just": ("just", "--dry-run", "check"), "make": ("make", "-n", "check")}
_PORT = "port each target to a recipe (same names; loops go in shebang recipes; no backticks)"


def _migration(ctx: Context) -> str:
    """Pin just where the repo already pins things: the pyproject's dev group for Python, mise.toml for every other stack."""
    if ctx.read("pyproject.toml") is not None:
        pin, run_it = "`uv add --dev rust-just`", "run it as `uv run just check`"
    else:
        pin, run_it = '`just = "<version>"` under [tools] in mise.toml, then `mise lock` (ADR 0024)', "run it as `just check`"
    return (
        f"move the Makefile to a justfile (ADR 0023): pin just with {pin}, {_PORT}, {run_it}, "
        "delete the Makefile; the shelf's own justfile is the reference"
    )


def runner(ctx: Context) -> Finding:
    """One runner for every repo, so blueprint reads the gate graph from one JSON dump (ADR 0023)."""
    if gate_graph.load(ctx) is None:
        return not_applicable("no gate: gate.one-command reports the missing one")
    if gate_graph.has_makefile_only(ctx):
        return failing("the gate is a Makefile; the shelf's runner is just (a justfile)", _migration(ctx))
    return passing("a justfile holds the gate")
