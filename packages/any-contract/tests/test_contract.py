"""Handshake, violation text and schema diff."""

from __future__ import annotations

import json

from any_contract import Violation, check_contract, diff_schema, undeclared


def test_matching_number_is_ok_object_or_text() -> None:
    assert check_contract(4, {"contract": 4}) is None
    assert check_contract(4, json.dumps({"contract": 4})) is None


def test_another_number_is_a_violation_with_a_bounded_excerpt() -> None:
    got = check_contract(4, {"contract": 3, "pad": "x" * 1000})
    assert isinstance(got, Violation)
    assert "not contract 4" in got.text and "contract=3" in got.text
    assert len(got.text) < 450


def test_not_json_and_not_an_object_are_violations() -> None:
    not_json = check_contract(4, "oops")
    not_object = check_contract(4, [1])
    assert not_json is not None and "not JSON" in not_json.text
    assert not_object is not None and "not an object" in not_object.text
    assert check_contract(4, None) is not None
    assert check_contract(4, {}) is not None


def test_capabilities_are_required_as_a_list_or_a_string() -> None:
    assert check_contract(4, {"contract": 4, "capabilities": ["a", "b"]}, capabilities=["a"]) is None
    assert check_contract(4, {"contract": 4, "capabilities": "a"}, capabilities=["a"]) is None
    got = check_contract(4, {"contract": 4, "capabilities": ["a"]}, capabilities=["a", "w"])
    assert got is not None and "capability w" in got.text
    assert check_contract(4, {"contract": 4}, capabilities=["w"]) is not None
    assert check_contract(4, {"contract": 4, "capabilities": 7}, capabilities=["w"]) is not None


def test_a_custom_key() -> None:
    assert check_contract(2, {"v": 2}, key="v") is None
    assert check_contract(2, {"contract": 2}, key="v") is not None


def test_identical_schemas_do_not_differ() -> None:
    s = {"type": "object", "required": ["a"], "properties": {"a": {"enum": [1, 2]}, "b": {}}}
    assert diff_schema(s, s) == {}


def test_fields_and_enums_differ_at_their_path() -> None:
    want = {"properties": {"a": {"enum": [1, 2]}, "b": {}}}
    have = {"properties": {"a": {"enum": [2, 3]}, "c": {}}}
    assert diff_schema(want, have) == {".fields": (("b",), ("c",)), ".a.enum": ((1,), (3,))}


def test_it_walks_required_items_additional_properties_and_unions() -> None:
    want = {
        "required": ["x"],
        "properties": {
            "rows": {"items": {"properties": {"p": {}}}},
            "m": {"additionalProperties": {"properties": {"q": {}}}},
            "u": {"anyOf": [{"properties": {"r": {}}}]},
        },
    }
    have = {
        "properties": {
            "x": {},
            "rows": {"items": {"properties": {}}},
            "m": {"additionalProperties": {"properties": {}}},
            "u": {"anyOf": [{}, {"properties": {"s": {}}}]},
        }
    }
    got = diff_schema(want, have)
    assert got[".rows[].fields"] == (("p",), ())
    assert got[".m{}.fields"] == (("q",), ())
    assert got[".u.anyOf[0].fields"] == (("r",), ())
    assert got[".u.anyOf[1].fields"] == ((), ("s",))
    assert ".fields" not in got  # x is required on one side and a property on the other: the same field


def test_undeclared_reports_new_and_resolved() -> None:
    found = {".a.fields": (("p",), ()), ".b.enum": ((1,), (2,))}
    known = {".a.fields": (("p",), (), "why"), ".gone.fields": (("z",), (), "fixed since")}
    assert undeclared(found, known) == ([".b.enum"], [".gone.fields"])


def test_a_known_drift_that_changed_is_both_new_and_resolved() -> None:
    found = {".a.fields": (("p", "q"), ())}
    known = {".a.fields": (("p",), (), "why")}
    assert undeclared(found, known) == ([".a.fields"], [".a.fields"])
