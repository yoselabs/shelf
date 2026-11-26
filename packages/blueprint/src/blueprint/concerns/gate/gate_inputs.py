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


# Why a step may run on any change. Closed: a lazy `*` has no kind to name, so it is found without reading shell.
WIDE_KINDS = {
    "change-set": "its input is the change set itself (a spell check, a secret scan over commits)",
    "self-keyed": "it keys its own inputs finer than the engine can (test units hash what each reaches)",
    "reads-everything": "its answer depends on the whole tree (the blueprint audit, the profile a render is made from)",
    "outside-files": "its answer depends on something outside the tree (git tags, a database, a network service)",
}


def wide_inputs(ctx: Context) -> Finding:
    """A step declared `["*"]` runs on any change; each says why in `[wide]`, with one of `WIDE_KINDS`. New: warns first (ADR 0018).

    The row does not judge what a recipe reads (free-form shell hides tool config files: narrowing from what a script seems to read is
    the worse error). It makes the owner of a `*` say why it is not narrower, from a closed list.
    """
    gate = gate_graph.load(ctx)
    text = ctx.read(FILE)
    if gate is None or not gate.stepped or text is None:
        return not_applicable("no declared step inputs to judge")
    table = tomllib.loads(text)
    wide = [step for step in gate.stepped if isinstance(table.get(step), list) and "*" in table[step]]
    given = table.get("wide")
    reasons: dict[str, object] = given if isinstance(given, dict) else {}
    unreasoned = [step for step in wide if not _has_kind(reasons.get(step))]
    stale = [step for step in reasons if step not in wide]
    if unreasoned:
        return failing(f"{', '.join(unreasoned)} run on any change and say no reason in [wide] ({FILE})", _WIDE_REMEDY)
    if stale:
        return failing(
            f"[wide] in {FILE} names {', '.join(stale)}, which no longer declares `*`",
            f"delete the stale [wide] entries ({', '.join(stale)})",
        )
    return passing(f"{len(wide)} steps run on any change, each with its reason" if wide else "no step runs on any change")


def _has_kind(reason: object) -> bool:
    return isinstance(reason, str) and any(
        reason.startswith(f"{kind}: ") and reason.removeprefix(f"{kind}: ").strip() for kind in WIDE_KINDS
    )


_WIDE_REMEDY = (
    f'narrow the step to the files it reads, or add `[wide]` to {FILE} with `<step> = "<kind>: <why>"`; kinds: '
    + "; ".join(f"{kind} ({meaning})" for kind, meaning in WIDE_KINDS.items())
    + ". When unsure what a tool reads (config discovery, lockfiles), keep `*`: an under-declared step skips a change that breaks it"
)
