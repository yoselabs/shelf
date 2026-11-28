"""A gate blueprint cannot read is not a gate with nothing to judge: rows that read the gate say so instead of `not applicable`."""

from __future__ import annotations

from blueprint import gate_graph
from blueprint.model import Context, Finding, not_checked, not_set_up


def unreadable(ctx: Context, what: str) -> Finding | None:
    """The finding for a row that reads the gate (`what`) when the gate is a Makefile only, or its justfile will not dump; else None.

    A repo with no gate at all keeps its rows `not applicable`: `gate.one-command` already reports the missing gate.
    """
    if gate_graph.has_makefile_only(ctx):
        return not_set_up(
            f"not set up because the gate is unreadable: the gate is a Makefile, which blueprint never reads, so {what} cannot be judged",
            "port the gate to a justfile (gate.runner has the steps)",
        )
    gate = gate_graph.load(ctx)
    if gate is not None and gate.unread:
        return not_checked(f"not checked because the gate is unreadable ({gate.unread}), so {what} cannot be judged")
    return None
