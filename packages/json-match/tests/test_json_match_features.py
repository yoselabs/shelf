"""json-match, stated as Gherkin: the steps here read and compare a value held by the scenario."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest
from json_match import MISSING, compare, dig, matches
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features")


@dataclass
class Held:
    value: Any = None
    read: Any = None
    failure: Exception | None = field(default=None)


@pytest.fixture
def held() -> Held:
    return Held()


@given("the value:")
def _value(held: Held, docstring: str) -> None:
    held.value = json.loads(docstring)


@when(parsers.parse('the path "{path}" is read'))
@when(parsers.re(r'the path "(?P<path>)" is read'))
def _read(held: Held, path: str) -> None:
    try:
        held.read = dig(held.value, path)
    except TypeError as exc:
        held.failure = exc


@then(parsers.parse("the value read is {read}"))
def _read_is(held: Held, read: str) -> None:
    if read == "missing":
        assert held.read is MISSING
    elif read == "the whole value":
        assert held.read == held.value
    else:
        assert held.read == json.loads(read)


@then(parsers.parse('the read fails with "{text}"'))
def _read_fails(held: Held, text: str) -> None:
    assert held.failure is not None
    assert text in str(held.failure)


@then(parsers.re(r'the value (?P<op>.+?) "(?P<text>.*)" is (?P<outcome>true|false)'))
def _compares(held: Held, op: str, text: str, outcome: str) -> None:
    assert compare(held.value, op, text) is (outcome == "true")


@then(parsers.parse('comparing with "{op}" fails with "{text}"'))
def _compare_fails(held: Held, op: str, text: str) -> None:
    with pytest.raises(ValueError, match=text):
        compare(held.value, op, "x")


@then(parsers.re(r"the value (?P<does>does|does not) match:"))
def _matches(held: Held, does: str, docstring: str) -> None:
    assert matches(json.loads(docstring), held.value) is (does == "does")
