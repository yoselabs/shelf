"""a2effect.testing's envelope reader and refusal step, stated as Gherkin."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from a2effect.testing import assert_refused, envelope_of
from a2effect.testing.steps import *  # noqa: F403 — the shipped step, registered here
from a2effect.testing.steps import the_call_is_refused_with
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features")


@dataclass
class World:
    received: Any = None
    envelope: dict[str, Any] | None = None
    failure: AssertionError | None = None
    last: Any = None
    error: dict[str, Any] | None = None
    seen: list[Any] = field(default_factory=list)


@pytest.fixture
def world() -> World:
    return World()


@pytest.fixture
def outcome(world: World) -> World:
    return world


def _envelope(code: str) -> dict[str, Any]:
    return {"code": code, "message": "nothing there", "hint": None, "retryable": False, "details": {"ref": "note/7"}}


def _as(code: str, form: str) -> Any:
    body = {"error": _envelope(code)}
    return {
        "an MCP result's structure": SimpleNamespace(structured_content=body, content=[SimpleNamespace(text="Not found")]),
        "an MCP result's text block": SimpleNamespace(structured_content=None, content=[SimpleNamespace(text=json.dumps(body))]),
        "an HTTP body": body,
        "the body's JSON text": json.dumps(body),
        "the bare envelope": _envelope(code),
    }[form]


@given(parsers.parse('a refusal with code "{code}" received as {form}'))
def _received_as(world: World, code: str, form: str) -> None:
    world.received = _as(code, form)


@given(parsers.parse("{what} received"))
def _received(world: World, what: str) -> None:
    world.received = {
        "a body without an error": {"items": []},
        "an MCP result with nothing": SimpleNamespace(structured_content=None, content=[]),
        "a JSON list": "[1, 2]",
    }[what]


@given("a call that succeeded")
def _succeeded(world: World) -> None:
    world.last, world.error, world.received = {"ok": True}, None, None


@given(parsers.parse('a call refused with "{code}"'))
def _refused(world: World, code: str) -> None:
    world.last, world.error = None, _envelope(code)


@when("its envelope is read")
def _read(world: World) -> None:
    try:
        world.envelope = envelope_of(world.received)
    except AssertionError as exc:
        world.failure = exc


@when(parsers.parse('it is asserted refused with "{code}"'))
def _assert(world: World, code: str) -> None:
    try:
        assert_refused(world.received, code)
    except AssertionError as exc:
        world.failure = exc


@when(parsers.parse('the shipped step checks for "{code}"'))
def _shipped(world: World, code: str) -> None:
    try:
        the_call_is_refused_with(world, code)
    except AssertionError as exc:
        world.failure = exc


@then(parsers.parse('the envelope\'s code is "{code}"'))
def _code_is(world: World, code: str) -> None:
    assert world.envelope is not None
    assert world.envelope["code"] == code


@then(parsers.parse('the envelope\'s details hold "{key}" = "{value}"'))
def _details(world: World, key: str, value: str) -> None:
    assert world.envelope is not None
    assert world.envelope["details"][key] == value


@then(parsers.parse('reading fails with "{text}"'))
@then(parsers.parse('the assertion fails with "{text}"'))
def _fails(world: World, text: str) -> None:
    assert world.failure is not None, "nothing failed"
    assert text in str(world.failure), str(world.failure)
