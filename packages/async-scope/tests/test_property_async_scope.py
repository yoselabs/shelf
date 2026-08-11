"""Property-based tests, additive on top of the failure-shaped example suite.

See docs/runbooks/property-based-testing.md. The module docstring names three
invariants precisely (LIFO teardown, no resource stranded by an earlier failure,
record-after-enter) that the example suite checks at one fixed N (typically 2-3
resources, one concurrency test fixed at N=20) — these generalize each to an
arbitrary N and an arbitrary failure pattern.

Written as sync tests driving `asyncio.run()` internally rather than `async def` +
`@given`, since Hypothesis's example-replay loop and pytest-asyncio's per-test event
loop don't compose cleanly — this sidesteps that entirely.
"""

from __future__ import annotations

import asyncio
from typing import Any, Self

import pytest
from async_scope import Lazy, ResourceScope, memoized
from hypothesis import given, settings
from hypothesis import strategies as st


class _Res:
    def __init__(self, log: list[str], name: str, *, fail_exit: bool = False) -> None:
        self.log = log
        self.name = name
        self.fail_exit = fail_exit

    async def __aenter__(self) -> Self:
        self.log.append(f"enter:{self.name}")
        return self

    async def __aexit__(self, *_: object) -> None:
        if self.fail_exit:
            msg = f"{self.name} refused to close"
            raise RuntimeError(msg)
        self.log.append(f"exit:{self.name}")


@given(fail_mask=st.lists(st.booleans(), min_size=1, max_size=8))
@settings(max_examples=100, deadline=None)
def test_property_teardown_is_always_lifo_regardless_of_failures(fail_mask: list[bool]) -> None:
    """For any count and any pattern of which resources fail to close, every
    resource is still exited (its name reaches the log), and among the ones
    that DO close successfully, the order is exactly reverse-of-entry.
    """

    async def run() -> tuple[list[str], BaseException | None]:
        log: list[str] = []
        scope = ResourceScope()
        names = [f"r{i}" for i in range(len(fail_mask))]
        for name, fails in zip(names, fail_mask, strict=True):
            await scope.enter(_Res(log, name, fail_exit=fails))
        caught: BaseException | None = None
        try:
            await scope.aclose()
        except Exception as exc:  # noqa: BLE001 — capturing to assert on, not swallowing
            caught = exc
        return log, caught

    log, caught = asyncio.run(run())

    entered = [line.removeprefix("enter:") for line in log if line.startswith("enter:")]
    exited = [line.removeprefix("exit:") for line in log if line.startswith("exit:")]
    expected_entered = [f"r{i}" for i in range(len(fail_mask))]
    expected_exited_in_order = [f"r{i}" for i in reversed(range(len(fail_mask))) if not fail_mask[i]]

    assert entered == expected_entered
    assert exited == expected_exited_in_order
    assert (caught is not None) == any(fail_mask)


@given(n_success=st.integers(min_value=0, max_value=6))
@settings(max_examples=50, deadline=None)
def test_property_a_resource_that_fails_to_enter_is_never_torn_down(n_success: int) -> None:
    """record-after-enter, generalized: for any number of successfully-entered
    resources followed by one that fails to open, the failing one never appears
    in the teardown log, and the successful ones still close in LIFO order.
    """

    class _FailingEnter:
        async def __aenter__(self) -> Self:
            msg = "refused to open"
            raise RuntimeError(msg)

        async def __aexit__(self, *_: object) -> None:  # pragma: no cover - must never run
            pytest.fail("a resource that failed to enter must never be exited")  # ty: ignore[invalid-argument-type]

    async def run() -> list[str]:
        log: list[str] = []
        scope = ResourceScope()
        names = [f"r{i}" for i in range(n_success)]
        for name in names:
            await scope.enter(_Res(log, name))
        with pytest.raises(RuntimeError, match="refused to open"):
            await scope.enter(_FailingEnter())
        await scope.aclose()
        return log

    log = asyncio.run(run())
    exited = [line.removeprefix("exit:") for line in log if line.startswith("exit:")]
    assert exited == [f"r{i}" for i in reversed(range(n_success))]


@given(n=st.integers(min_value=1, max_value=50))
@settings(max_examples=30, deadline=None)
def test_property_memoized_builds_exactly_once_for_any_concurrency(n: int) -> None:
    """Generalizes test_memoized_builds_once_under_concurrency beyond the one
    fixed N=20 in the example suite.
    """

    async def run() -> tuple[int, list[Any]]:
        builds = 0

        async def _factory() -> object:
            nonlocal builds
            builds += 1
            await asyncio.sleep(0.001)
            return object()

        thunk: Lazy[object] = memoized(_factory)
        results = await asyncio.gather(*(thunk() for _ in range(n)))
        return builds, results

    builds, results = asyncio.run(run())
    assert builds == 1
    assert all(r is results[0] for r in results)
