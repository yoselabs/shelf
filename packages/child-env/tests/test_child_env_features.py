"""child-env's scrub rules, stated as Gherkin."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from child_env import scrub
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features")


@dataclass
class World:
    env: dict[str, str] = field(default_factory=dict)
    snapshot: dict[str, str] = field(default_factory=dict)
    out: dict[str, str] = field(default_factory=dict)


@pytest.fixture
def world() -> World:
    return World()


def _names(text: str) -> list[str]:
    return [n.strip() for n in text.split(",") if n.strip()]


@given(parsers.parse('the environment has {name} set to "{value}"'))
def _set(world: World, name: str, value: str) -> None:
    world.env[name] = value


@when("the environment is scrubbed")
def _scrub(world: World) -> None:
    world.snapshot = dict(world.env)
    world.out = scrub(world.env)


@when(parsers.parse('the environment is scrubbed keeping "{keep}"'))
def _scrub_keep(world: World, keep: str) -> None:
    world.out = scrub(world.env, keep=_names(keep))


@when(parsers.parse('the environment is scrubbed dropping "{drop}"'))
def _scrub_drop(world: World, drop: str) -> None:
    world.out = scrub(world.env, drop=_names(drop))


@when(parsers.parse('the environment is scrubbed keeping "{keep}" and dropping "{drop}"'))
def _scrub_both(world: World, keep: str, drop: str) -> None:
    world.out = scrub(world.env, keep=_names(keep), drop=_names(drop))


@then(parsers.parse("{name} is gone"))
def _gone(world: World, name: str) -> None:
    assert name not in world.out


@then(parsers.parse("{name} stays"))
def _stays(world: World, name: str) -> None:
    assert name in world.out
    if name in world.env:
        assert world.out[name] == world.env[name]


@then(parsers.parse('{name} is "{value}"'))
def _is(world: World, name: str, value: str) -> None:
    assert world.out[name] == value


@then("the input still has CLAUDECODE and PATH")
def _unmutated(world: World) -> None:
    assert world.env == world.snapshot
    assert "CLAUDECODE" in world.env
    assert "PATH" in world.env


@then("the result is a different dict")
def _different(world: World) -> None:
    assert world.out is not world.env
