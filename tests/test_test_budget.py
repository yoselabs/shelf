"""tools/test_budget/test_budget.py: a test over its call-time budget fails; its own `slow` mark raises the ceiling."""

from __future__ import annotations

import pytest

_SLEEPY = """
import time
import pytest

def test_over():
    time.sleep(0.3)

@pytest.mark.slow(budget=5, reason="measured")
def test_over_with_its_own_budget():
    time.sleep(0.3)

def test_under():
    pass
"""


@pytest.fixture
def small_budget(pytester: pytest.Pytester) -> None:
    pytester.makeini("[pytest]\nasyncio_default_fixture_loop_scope = function\ntest_budget_s = 0.1\n")


def test_an_unmarked_test_over_budget_fails_and_a_marked_one_passes(pytester: pytest.Pytester, small_budget: None) -> None:
    pytester.makepyfile(_SLEEPY)
    result = pytester.runpytest_inprocess("-p", "tools.test_budget.test_budget")
    result.assert_outcomes(passed=2, failed=1)
    result.stdout.fnmatch_lines(["*over its time budget*"])


def test_the_budget_is_not_charged_to_a_test_that_fails_for_its_own_reason(pytester: pytest.Pytester, small_budget: None) -> None:
    pytester.makepyfile("import time\n\ndef test_broken():\n    time.sleep(0.3)\n    assert False, 'its own failure'\n")
    result = pytester.runpytest_inprocess("-p", "tools.test_budget.test_budget")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*its own failure*"])
