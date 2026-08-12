"""The operation contract (`tools/onboard/operations.py`), against a trivial
reference operation — never a real one. The contract is the deliverable;
`guard`/`beads`/etc. are instances of it, tested separately.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools"))

from onboard.operations import Outcome, Result, run_all  # noqa: E402  -- path-injected, after sys.path setup


@dataclass
class _Counter:
    """A trivial operation: applies once, counts how many times `run` executed.

    Used to prove idempotence (D3.1) and effect-assertion (D3.3) without any
    onboarding-specific behaviour muddying what the harness itself guarantees.
    """

    name: str = "counter"
    requires: tuple[str, ...] = ()
    calls: list[int] = field(default_factory=lambda: [0])
    verify_calls: list[int] = field(default_factory=lambda: [0])
    should_verify: bool = True

    def run(self, results: dict[str, Result]) -> Result:
        self.calls[0] += 1
        self.verify_calls[0] += 1
        if not self.should_verify:
            return Result(Outcome.FAILED, verified=False, message="did not verify")
        return Result(Outcome.APPLIED, verified=True, message=f"applied (call {self.calls[0]})")


@dataclass
class _Dependent:
    """Declares a dependency on `counter`. `run` is only ever called once the
    harness has already confirmed that dependency is satisfied — see `operations.py`."""

    name: str = "dependent"
    requires: tuple[str, ...] = ("counter",)

    def run(self, results: dict[str, Result]) -> Result:
        return Result(Outcome.APPLIED, verified=True)


@dataclass
class _Reckless:
    """An operation that would happily report success regardless of its own
    declared `requires`. Exists to prove the HARNESS withholds the call rather
    than trusting the operation to check itself — see the test below.
    """

    name: str = "reckless"
    requires: tuple[str, ...] = ("missing",)
    calls: list[int] = field(default_factory=lambda: [0])

    def run(self, results: dict[str, Result]) -> Result:
        self.calls[0] += 1
        return Result(Outcome.APPLIED, verified=True)


# --- D3.1 idempotent -------------------------------------------------------


def test_running_twice_reports_the_same_outcome() -> None:
    op = _Counter()
    first = run_all([op])["counter"]
    second = run_all([op])["counter"]

    assert first.outcome == second.outcome == Outcome.APPLIED
    assert first.verified and second.verified


# --- D3.2 precondition-checked ----------------------------------------------


def test_dependent_refuses_when_its_dependency_never_ran() -> None:
    results = run_all([_Dependent()])
    assert results["dependent"].outcome == Outcome.FAILED


def test_harness_withholds_the_call_rather_than_trusting_the_operation_to_self_check() -> None:
    """The harness — not operation goodwill — is what enforces guarantee 2.

    `_Reckless` would report APPLIED unconditionally if invoked; the harness
    must never invoke it once its `requires` is unmet.
    """
    op = _Reckless()
    results = run_all([op])

    assert op.calls[0] == 0, "operation ran despite an unmet precondition"
    assert results["reckless"].outcome == Outcome.FAILED


def test_dependent_proceeds_once_its_dependency_is_applied_and_verified() -> None:
    results = run_all([_Counter(), _Dependent()])
    assert results["dependent"].outcome == Outcome.APPLIED


# --- D3.3 / D3.4 present-but-unverified is not satisfied --------------------


def test_present_but_unverified_dependency_still_blocks_the_dependent() -> None:
    """The distinction the whole design rests on (D3 guarantee 2 vs 3): an
    operation that ran and reported FAILED (could not verify its own effect)
    must not satisfy a dependent's precondition, even though it "ran"."""
    unverified_counter = _Counter(should_verify=False)

    results = run_all([unverified_counter, _Dependent()])

    assert results["counter"].outcome == Outcome.FAILED
    assert results["dependent"].outcome == Outcome.FAILED


def test_three_distinct_outcomes_are_not_collapsed() -> None:
    assert Outcome.APPLIED is not Outcome.FAILED
    assert Outcome.FAILED is not Outcome.COULD_NOT_APPLY
    assert Outcome.APPLIED is not Outcome.COULD_NOT_APPLY


def test_could_not_apply_is_not_satisfied_either() -> None:
    """COULD_NOT_APPLY must not be mistaken for success by a dependent, same as FAILED."""

    @dataclass
    class _Unavailable:
        name: str = "unavailable"
        requires: tuple[str, ...] = ()

        def run(self, results: dict[str, Result]) -> Result:
            return Result(Outcome.COULD_NOT_APPLY, verified=False, message="prerequisite tool not installed")

    results = run_all([_Unavailable(), _Dependent()])
    assert results["unavailable"].outcome == Outcome.COULD_NOT_APPLY
    assert results["dependent"].outcome == Outcome.FAILED
