"""Two edits of one YAML document merge by structure, not by line.

Git conflicts when both branches append to one list or touch neighbouring keys,
though they changed different things. `merge3` takes every change only one side
made, raises `MergeConflictError` naming the path where both changed one value
differently, and writes the result into `ours`' document so its comments stay.
"""

from __future__ import annotations

import io

import pytest
from ruamel.yaml import YAML
from yaml_merge import MergeConflictError, merge3

_YAML = YAML(typ="rt")
_YAML.indent(mapping=2, sequence=4, offset=2)


def _merge_text(base: str, ours: str, theirs: str) -> str:
    buf = io.StringIO()
    _YAML.dump(merge3(_YAML.load(base), _YAML.load(ours), _YAML.load(theirs)), buf)
    return buf.getvalue()


@pytest.mark.parametrize(
    ("base", "ours", "theirs", "merged"),
    [
        pytest.param({"a": 1, "b": 1}, {"a": 2, "b": 1}, {"a": 1, "b": 3}, {"a": 2, "b": 3}, id="each side changed its own key"),
        pytest.param({"a": 1}, {"a": 2}, {"a": 2}, {"a": 2}, id="both made the same change"),
        pytest.param({"a": 1}, {"a": 1, "b": 2}, {"a": 1, "c": 3}, {"a": 1, "b": 2, "c": 3}, id="both added keys"),
        pytest.param({"a": 1, "b": 2}, {"a": 1, "b": 2}, {"a": 1}, {"a": 1}, id="theirs dropped a key ours kept"),
        pytest.param(None, {"a": 1}, {"b": 2}, {"a": 1, "b": 2}, id="both created the file"),
        pytest.param({"a": 1}, None, {"a": 1}, None, id="ours emptied, theirs untouched"),
        pytest.param(
            {"items": [{"id": "x", "v": 1}]},
            {"items": [{"id": "x", "v": 2}]},
            {"items": [{"id": "x", "v": 1}, {"id": "y", "v": 1}]},
            {"items": [{"id": "x", "v": 2}, {"id": "y", "v": 1}]},
            id="list entries pair by identity",
        ),
        pytest.param(
            [{"name": "x"}, {"name": "y"}],
            [{"name": "y"}, {"name": "x"}],
            [{"name": "x"}],
            [{"name": "x"}],
            id="a top-level list: theirs dropped an entry ours only moved",
        ),
    ],
)
def test_changes_made_on_one_side_are_taken(base: object, ours: object, theirs: object, merged: object) -> None:
    assert merge3(base, ours, theirs) == merged


@pytest.mark.parametrize(
    ("base", "ours", "theirs", "path"),
    [
        pytest.param({"a": {"b": 1}}, {"a": {"b": 2}}, {"a": {"b": 3}}, ("a", "b"), id="one value, two changes"),
        pytest.param({"a": 1}, {}, {"a": 2}, ("a",), id="ours deleted what theirs changed"),
        pytest.param(
            {"items": [{"id": "x", "v": 1}]},
            {"items": [{"id": "x", "v": 2}]},
            {"items": [{"id": "x", "v": 3}]},
            ("items", "x", "v"),
            id="an entry is named by its identity",
        ),
        pytest.param({"l": [1]}, {"l": [1, 2]}, {"l": [1, 3]}, ("l",), id="a list without identity"),
        pytest.param({"l": [{"id": 1}]}, {"l": [{"id": 1}, {"id": 2}]}, {"l": [{"id": 1}, {"id": 1}]}, ("l",), id="a duplicate identity"),
        pytest.param(1, 2, 3, (), id="the document itself"),
    ],
)
def test_a_value_both_sides_changed_differently_is_a_conflict(base: object, ours: object, theirs: object, path: tuple[object, ...]) -> None:
    with pytest.raises(MergeConflictError) as raised:
        merge3(base, ours, theirs)

    assert raised.value.path == path


def test_ours_comments_survive_and_theirs_entry_arrives() -> None:
    base = "rules:\n  -   id: r1\n      text: old\n"
    ours = "# why these rules exist\nrules:\n  -   id: r1\n      # agreed with the owner\n      text: new\n"
    theirs = "rules:\n  -   id: r1\n      text: old\n  -   id: r2\n      text: added\n"

    out = _merge_text(base, ours, theirs)

    assert out == (
        "# why these rules exist\nrules:\n  - id: r1\n      # agreed with the owner\n    text: new\n  - id: r2\n    text: added\n"
    )


def test_base_and_theirs_are_never_mutated() -> None:
    base = {"a": [{"id": "x"}]}
    theirs = {"a": [{"id": "x"}, {"id": "y"}]}

    merge3(base, _YAML.load("a:\n  - id: x\n"), theirs)

    assert base == {"a": [{"id": "x"}]}
    assert theirs == {"a": [{"id": "x"}, {"id": "y"}]}
