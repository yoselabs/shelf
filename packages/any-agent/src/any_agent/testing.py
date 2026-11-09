"""Semantic double for the four-positional-argument supervised execution call.

No processes or timing are simulated. Ref callbacks must be bounded and nonraising,
as required by the consumer's real output-pump composition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from any_agent.protocol import Harness, LaunchSpec
    from any_agent.supervisor import RunHooks, RunOutcome


class FakeRun:
    """One configured execution: registration, observed refs, then unchanged raw outcome.

    The caller composes the same decode_answer after real and fake execution. This
    subset does not emulate run's optional observers, process control or stop proof.
    """

    def __init__(self, outcome: RunOutcome, *, refs: tuple[str, ...] = ()) -> None:
        if outcome.worker is None:
            msg = "FakeRun requires an explicit outcome.worker fixture"
            raise ValueError(msg)
        if refs and "ref" in outcome.summary.res and outcome.summary.res["ref"] != refs[-1]:
            msg = "FakeRun final observed ref must match the reported terminal ref"
            raise ValueError(msg)
        self._outcome, self._worker, self._refs = outcome, outcome.worker, refs
        self.calls: list[tuple[Harness, LaunchSpec, float, RunHooks | None]] = []

    def __call__(
        self,
        harness: Harness,
        spec: LaunchSpec,
        timeout: float,
        hooks: RunHooks | None = None,
    ) -> RunOutcome:
        """Consume once; registration refusal propagates before refs or terminal return."""
        if self.calls:
            msg = "FakeRun execution already consumed"
            raise RuntimeError(msg)
        self.calls.append((harness, spec, timeout, hooks))
        if hooks is not None:
            if hooks.started is not None:
                hooks.started(self._worker)
            if hooks.ref is not None:
                for ref in self._refs:
                    hooks.ref(ref)
        return self._outcome
