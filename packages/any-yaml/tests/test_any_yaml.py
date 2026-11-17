"""Behaviour of any-yaml through its public API."""

from __future__ import annotations

from typing import TYPE_CHECKING

import any_yaml
import pytest
from any_yaml import (
    MergeConflictError,
    YAMLError,
    append_item,
    append_item_file,
    dump,
    flow_lines,
    load,
    merge3_text,
    merge_text,
    read,
    write,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_load_is_yaml_12_and_fresh() -> None:
    first = load("on: yes\nn: 010\n")
    assert first == {"on": "yes", "n": 10}
    assert isinstance(first, dict)
    first["on"] = "changed"
    assert load("on: yes\nn: 010\n") == {"on": "yes", "n": 10}


def test_load_malformed_raises_yamlerror() -> None:
    with pytest.raises(YAMLError):
        load("a: [1, 2\n")


def test_read_is_cached_and_cannot_be_mutated() -> None:
    data = read("a: {b: [1, 2]}\n")
    assert data is read("a: {b: [1, 2]}\n")
    assert isinstance(data, dict | type(read("a: 1\n")))
    with pytest.raises(TypeError):
        data["a"] = 1  # type: ignore[index]
    inner = data["a"]  # type: ignore[index]
    with pytest.raises(TypeError):
        inner["b"] = 1
    assert inner["b"] == (1, 2)


def test_dump_is_block_style_one_field_per_line() -> None:
    assert dump({"a": 1, "b": {"c": [1, 2]}}) == "a: 1\nb:\n  c:\n  - 1\n  - 2\n"


def test_merge_text_keeps_comments_and_order() -> None:
    existing = "# top\nz: 1  # why\n\na: 2\n"
    assert merge_text(existing, {"a": 3, "z": 1}) == "# top\nz: 1  # why\n\na: 3\n"


def test_merge3_text_merges_distinct_edits_and_conflicts() -> None:
    base = "- id: a\n  v: 1\n- id: b\n  v: 1\n"
    ours = "- id: a\n  v: 2\n- id: b\n  v: 1\n"
    theirs = "- id: a\n  v: 1\n- id: b\n  v: 3\n"
    assert load(merge3_text(base, ours, theirs) or "") == [{"id": "a", "v": 2}, {"id": "b", "v": 3}]
    with pytest.raises(MergeConflictError):
        merge3_text(base, ours, "- id: a\n  v: 9\n- id: b\n  v: 1\n")


@pytest.mark.parametrize(
    "text",
    [
        'say "hi"',
        "back\\slash",
        "a: b",
        "#tag",
        "1e3",
        "yes",
        "",
        " pad ",
        "tab\there",
        "multi\nline",
        "é ünï",
        "- dash",
        "{x}",
        "key: 'q'",
    ],
)
def test_flow_lines_round_trips_any_text(text: str) -> None:
    mapping = {"k": {"own": text, "deps": {text: text}, "covers": [text], "empty": {}, "none": []}}
    rendered = flow_lines(mapping)
    assert load(rendered) == mapping
    assert rendered.count("\n") == 1


def test_flow_lines_is_one_sorted_line_per_key() -> None:
    rendered = flow_lines({"b/2": {"own": "x", "covers": ["a", "b"]}, "a/1": {"own": "y", "deps": {}}})
    assert rendered == "a/1: {own: y, deps: {}}\nb/2: {own: x, covers: [a, b]}\n"
    assert flow_lines({}) == ""


def test_append_item_leaves_earlier_text_untouched() -> None:
    text = "format: 1\nitems:\n  # first\n  - id: a\n    n: 1\n\n  - id: b\n    n: 2\n"
    result = append_item(text, "items", {"id": "c", "n": 3})
    assert result.startswith(text)
    assert load(result) == {"format": 1, "items": [{"id": "a", "n": 1}, {"id": "b", "n": 2}, {"id": "c", "n": 3}]}
    assert result.endswith("  - id: c\n    n: 3\n")


def test_append_item_keeps_what_follows_the_list_and_flush_indent() -> None:
    text = "items:\n- id: a\ntail: 1  # keep\n"
    result = append_item(text, "items", {"id": "b"})
    assert result == "items:\n- id: a\n- id: b\ntail: 1  # keep\n"


def test_append_item_creates_the_list() -> None:
    assert append_item("", "items", {"id": "a"}) == "items:\n  - id: a\n"
    assert append_item("format: 1", "items", {"id": "a"}) == "format: 1\nitems:\n  - id: a\n"
    assert append_item("items: []\n", "items", {"id": "a"}) == "items:\n  - id: a\n"


def test_append_item_refuses_what_it_cannot_extend() -> None:
    with pytest.raises(TypeError, match="not a list"):
        append_item("items: 3\n", "items", 1)
    with pytest.raises(ValueError, match="not a block list"):
        append_item("items: [a, b]\n", "items", "c")
    with pytest.raises(TypeError, match="not a mapping"):
        append_item("- a\n", "items", 1)


def test_append_item_quotes_awkward_text() -> None:
    result = append_item("items:\n  - x\n", "items", 'say "hi": \\ #')
    assert load(result) == {"items": ["x", 'say "hi": \\ #']}


def test_write_merges_into_an_existing_file_atomically(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "c.yml"
    write(path, {"a": 1})
    assert path.read_text() == "a: 1\n"
    path.write_text("# mine\nb: 0\na: 1  # note\n")
    write(path, {"a": 2, "b": 0})
    assert path.read_text() == "# mine\nb: 0\na: 2  # note\n"
    assert [p.name for p in path.parent.iterdir()] == ["c.yml"]


def test_append_item_file_starts_from_initial(tmp_path: Path) -> None:
    path = tmp_path / "d" / "removed.yml"
    append_item_file(path, "items", {"id": "a"}, initial="format: 1\n")
    append_item_file(path, "items", {"id": "b"})
    assert path.read_text() == "format: 1\nitems:\n  - id: a\n  - id: b\n"


def test_public_names() -> None:
    assert sorted(any_yaml.__all__) == sorted(
        [
            "MergeConflictError",
            "YAMLError",
            "append_item",
            "append_item_file",
            "dump",
            "flow_lines",
            "load",
            "merge3_text",
            "merge_text",
            "read",
            "write",
        ]
    )
