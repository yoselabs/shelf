"""The `verify` operation — re-check every previously-applied operation, per-operation.

The mechanism is deliberately thin: D3.1 already requires every operation to be
idempotent, and D3.3 already requires every `run()` to assert its effect rather
than trust an artifact. Re-running an operation IS re-verifying it — the same
check that caught a problem the first time catches it again, with no separate
"verify" code path to drift from the "apply" path.

This matters concretely for the config-revert trap
(`docs/runbooks/adopt-beads.md` §1.2, landmine 5): `.beads/config.yaml` is a
tracked file, so `git checkout -- .beads/config.yaml` (or any tree-rewinding
git operation) can silently revert a `bd config set` with no signal from `bd`
itself. `beads.BeadsOperation.run()` unconditionally re-sets and re-reads back
its config keys on every call — so a second `verify` pass after a revert
re-applies and re-confirms, catching the drift rather than reporting a stale
pass.

`verify` never collapses per-operation results into one boolean on its own —
`all_satisfied` exists for a caller that genuinely needs a single gate, but the
per-operation dict is the primary artifact; D3.4 is exactly the guarantee that
a single aggregate must not hide which operation actually failed.
"""

from __future__ import annotations

from .operations import Operation, Result, run_all


def verify(operations: list[Operation]) -> dict[str, Result]:
    """Re-run `operations` (in the same order they were originally applied) and report per-operation."""
    return run_all(operations)


def all_satisfied(results: dict[str, Result]) -> bool:
    """A single yes/no gate over `results` — never a substitute for showing the per-operation breakdown."""
    return all(result.satisfied for result in results.values())
