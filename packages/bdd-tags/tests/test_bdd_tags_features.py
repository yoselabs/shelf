"""bdd-tags, stated as Gherkin: each scenario runs a small suite in a pytester sandbox."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

if TYPE_CHECKING:
    from pytest import RunResult

scenarios("features")

_TEST_MODULE = """
from pytest_bdd import given, scenarios

scenarios("probe.feature")


@given("it passes")
def _passes() -> None:
    pass


@given("it fails")
def _fails() -> None:
    raise AssertionError("it fails")
"""


@pytest.fixture
def run() -> dict[str, RunResult]:
    return {}


def _write(pytester: pytest.Pytester, tag: str, step: str) -> None:
    pytester.makefile(".feature", probe=f"Feature: Probe\n\n  {tag}\n  Scenario: The probe\n    Given {step}\n")
    pytester.makepyfile(test_probe=_TEST_MODULE)
    pytester.makeini("[pytest]\nasyncio_default_fixture_loop_scope = function\n")


@given(parsers.parse('a feature whose scenario {body} is tagged "{tag}"'))
def _tagged(pytester: pytest.Pytester, body: str, tag: str) -> None:
    _write(pytester, tag, f"it {body}")


@given("a feature whose scenario has a step nobody wrote")
def _unwritten(pytester: pytest.Pytester) -> None:
    _write(pytester, "", "nobody wrote this step")


@when("the suite runs with strict markers")
def _runs(pytester: pytest.Pytester, run: dict[str, RunResult]) -> None:
    run["result"] = pytester.runpytest("--strict-markers")


@then(parsers.parse("the scenario is reported as {outcome}"))
def _reported(run: dict[str, RunResult], outcome: str) -> None:
    outcomes = run["result"].parseoutcomes()
    expected = {"error": 1} if outcome == "errored" else {outcome: 1}
    got = {k.rstrip("s"): v for k, v in outcomes.items() if k in {"passed", "failed", "xfailed", "skipped", "errors", "error"}}
    assert got == {k.rstrip("s"): v for k, v in expected.items()}, run["result"].stdout.str()
