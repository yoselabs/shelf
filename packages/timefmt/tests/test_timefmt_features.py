"""timefmt's span, wait and count formats, stated as Gherkin."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from timefmt import fmt_span, fmt_until, human_count

scenarios("features")


@dataclass
class World:
    now: float = 0.0
    text: str = ""


@pytest.fixture
def world() -> World:
    return World()


@given(parsers.parse("the clock reads {now:d} seconds"))
def _clock(world: World, now: int) -> None:
    world.now = float(now)


@when(parsers.parse("the span of {seconds:d} seconds is formatted"))
def _span(world: World, seconds: int) -> None:
    world.text = fmt_span(seconds)


@when(parsers.parse("the wait until {when:d} seconds is formatted"))
def _until(world: World, when: int) -> None:
    world.text = fmt_until(float(when), now=world.now)


@when(parsers.parse("the count {n:d} is formatted"))
def _count(world: World, n: int) -> None:
    world.text = human_count(n)


@then(parsers.parse('it reads "{text}"'))
def _reads(world: World, text: str) -> None:
    assert world.text == text
