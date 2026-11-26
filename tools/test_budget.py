"""A pytest plugin: a test that runs longer than the budget fails, unless it names its own larger budget.

The 2026-11-26 profile found a test of 41 s in a 224 s suite, and a 10 s test that was only the real `bd` starting a
server. Nothing said so: a slow test grew silently. Now each test has `BUDGET_S` seconds of call time. A test that
needs more is marked `@pytest.mark.slow(budget=<seconds>, reason="<why it cannot be faster>")`; the mark is the row,
it names the new ceiling, so a regression past it fails too. The budget measures the call phase only, not fixtures.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

BUDGET_S = 20.0  # the slowest unmarked test of the 2026-11-26 run took 12.5 s under the parallel run's load


def budget_of(item: pytest.Item) -> float:
    """Seconds of call time this test may take: its `slow` mark's `budget`, else the `test_budget_s` ini value."""
    mark = item.get_closest_marker("slow")
    if mark is not None and "budget" in mark.kwargs:
        return float(mark.kwargs["budget"])
    return float(item.config.getini("test_budget_s"))


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addini("test_budget_s", "default call-time budget of a test, in seconds", default=str(BUDGET_S))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "slow(budget, reason): this test needs more than the default call-time budget; `budget` is its own ceiling in seconds."
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Generator[None, object, None]:
    outcome = yield
    report = outcome.get_result()  # type: ignore[attr-defined]
    if call.when != "call" or not report.passed:
        return
    budget = budget_of(item)
    if report.duration > budget:
        report.outcome = "failed"
        report.longrepr = (
            f"over its time budget: {report.duration:.1f}s of {budget:.0f}s. Make it faster, or mark it "
            f'`@pytest.mark.slow(budget={math.ceil(report.duration * 2)}, reason="<why it cannot be faster>")`.'
        )
