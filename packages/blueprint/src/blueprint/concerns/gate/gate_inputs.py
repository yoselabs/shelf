"""Gate step inputs: every step `check` runs declares the files it reads (`gate-inputs.toml`, ADR 0031)."""

from __future__ import annotations

import tomllib

from blueprint import gate_graph
from blueprint.model import Context, Finding, failing, not_applicable, passing

FILE = "gate-inputs.toml"


def step_inputs(ctx: Context) -> Finding:
    """Each name `check` hands to `steps` has a list of globs in gate-inputs.toml; no network. New checkpoints warn first (ADR 0018)."""
    gate = gate_graph.load(ctx)
    if gate is None or not gate.stepped:
        return not_applicable("the gate runs no `steps`")
    text = ctx.read(FILE)
    if text is None:
        return failing(f"no {FILE}: {', '.join(gate.stepped)} read undeclared files, so every commit runs them", _REMEDY)
    declared = {k for k, v in tomllib.loads(text).items() if isinstance(v, list) and v}
    missing = [s for s in gate.stepped if s not in declared]
    if missing:
        return failing(f"{FILE} declares no inputs for {', '.join(missing)}", _REMEDY)
    return passing(f"{len(gate.stepped)} steps declare their inputs")


_REMEDY = (
    f'add `<step> = ["<glob>", ...]` to {FILE} for each step: the files it reads (fnmatch, `*` crosses `/`); `["*"]` when it reads the '
    "whole repo. A step none of whose inputs changed is not started (any-gate)"
)
