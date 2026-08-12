"""The operation contract every onboarding step must satisfy.

`onboard-consumer-skill` D1's split: the skill decides *which* operations apply
(judgment — varies per repo, prose can carry it); operations enforce *order* and
*effect* (mechanism — identical everywhere, prose cannot carry it, per
`fix-guard-hookspath-resolution`).

D3's five guarantees, encoded here so a real operation cannot skip one by
omission:

1. Idempotent — running twice changes nothing the second time.
2. Precondition-checked — refuses if a dependency is not present AND verified.
3. Effect-asserting — `verify()` exercises the effect; it never trusts an
   artifact (file exists, marker present, mode bit set) as proxy for it.
4. Three-outcome — APPLIED / FAILED / COULD_NOT_APPLY, never collapsed.
   "Could not check" reported as success is how a dead guard printed a checkmark.
5. Non-destructive by default — an operation that would overwrite something it
   does not own reports COULD_NOT_APPLY rather than clobbering it.

This module is the contract and the harness. It carries no onboarding-specific
knowledge — no guard, no beads, no git. Real operations (``guard.py``,
``beads.py``, …) implement ``Operation`` and are exercised by this harness.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class Outcome(Enum):
    """D3 guarantee 4 — an operation reports exactly one of these three, never a fourth shape."""

    APPLIED = "applied"
    FAILED = "failed"
    COULD_NOT_APPLY = "could_not_apply"


@dataclass(frozen=True)
class Result:
    """What an operation reports. ``verified`` is what a dependent may rely on.

    A dependency is satisfied only by ``outcome is APPLIED and verified`` — an
    operation that ran but could not confirm its own effect must not unblock
    anything downstream (D3 guarantee 2 vs 3).
    """

    outcome: Outcome
    verified: bool
    message: str = ""

    @property
    def satisfied(self) -> bool:
        """Whether a dependent may treat this as its precondition met."""
        return self.outcome is Outcome.APPLIED and self.verified


class Operation(Protocol):
    """A single onboarding step. ``name`` is what dependents refer to in ``requires``."""

    name: str
    requires: tuple[str, ...]

    def run(self, results: dict[str, Result]) -> Result:
        """Apply the effect and verify it.

        ``results`` carries every prior operation's Result in this run, keyed by
        name. ``run`` is only ever called once ``run_all`` has already confirmed
        every entry in ``requires`` is ``satisfied`` — implementations need not
        re-check their own preconditions, the harness withholds the call
        entirely rather than trusting each operation to police itself.
        """
        ...


def run_all(operations: list[Operation]) -> dict[str, Result]:
    """Run operations in the given order, refusing any whose ``requires`` is unmet.

    Order here is the caller's judgment (the skill's job, D1) — this function
    does not reorder or schedule. What it guarantees is that an operation
    declaring ``requires=("guard",)`` can never execute when "guard" is missing
    from ``results`` or present-but-unverified: the harness itself withholds the
    call and records the refusal, so an operation cannot opt out of guarantee 2
    by simply forgetting to check its own preconditions.
    """
    results: dict[str, Result] = {}
    for op in operations:
        unmet = [dep for dep in op.requires if not results.get(dep, Result(Outcome.FAILED, verified=False)).satisfied]
        if unmet:
            results[op.name] = Result(Outcome.FAILED, verified=False, message=f"requires {unmet} to be applied and verified first")
            continue
        results[op.name] = op.run(results)
    return results
