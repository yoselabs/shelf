"""Gherkin steps over a refused call (pytest-bdd, the ``testing`` extra).

Import them into the conftest that collects your features::

    from a2effect.testing.steps import *  # noqa: F403

The steps read the ``outcome`` fixture, which the suite provides: any object whose ``error``
holds the last refusal's envelope (``None`` after a success) and whose ``last`` holds the last
result. It is read when the step runs, so the holder is what the fixture returns, never the
value.
"""

from __future__ import annotations

from typing import Any, Protocol

from pytest_bdd import parsers, then

from a2effect.testing import assert_refused


class Outcome(Protocol):
    """What the suite's ``outcome`` fixture returns: the last call's result or refusal."""

    @property
    def last(self) -> Any: ...
    @property
    def error(self) -> dict[str, Any] | None: ...


@then(parsers.parse('the call is refused with "{code}"'))
def the_call_is_refused_with(outcome: Outcome, code: str) -> None:
    if outcome.error is None:
        msg = f"expected {code}, the call succeeded: {outcome.last}"
        raise AssertionError(msg)
    assert_refused(outcome.error, code)
