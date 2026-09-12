"""Writing a payload back does not destroy the document a human wrote.

`model_dump` produces a plain dict, and dumping that over a file replaces it —
comments, blank lines and key order gone.

The split that matters: the payload is authoritative about VALUES, the existing
document is authoritative about everything else. The two tests at the bottom cover
the pair of ruamel behaviours a naive merge gets wrong (a comment above a key is
filed under the PREVIOUS key; a `CommentedSeq`'s comment map is keyed by index and
is cleared by slice assignment) — both found the hard way, in a2kay.
"""

from __future__ import annotations

import io

import pytest
from ruamel.yaml import YAML
from yaml_merge import merge_into

_YAML = YAML(typ="rt")
_YAML.preserve_quotes = True
_YAML.indent(mapping=2, sequence=4, offset=2)


def _roundtrip(document: str, payload: dict[str, object]) -> str:
    buf = io.StringIO()
    _YAML.dump(merge_into(_YAML.load(document), payload), buf)
    return buf.getvalue()


def test_a_comment_above_a_key_survives() -> None:
    out = _roundtrip("# why this type exists\nname: note\n", {"name": "note"})

    assert "# why this type exists" in out


def test_a_trailing_comment_on_a_line_survives_a_value_change() -> None:
    out = _roundtrip("file_pattern: Notes/{slug}.md  # flat\n", {"file_pattern": "Notes/{id}.md"})

    assert "# flat" in out
    assert "Notes/{id}.md" in out


def test_blank_lines_and_key_order_survive() -> None:
    document = "name: note\n\nwhen_to_use: anything\n"

    out = _roundtrip(document, {"when_to_use": "anything", "name": "note"})

    assert out == document  # payload order does not reorder the author's file


def test_a_new_key_is_appended() -> None:
    out = _roundtrip("name: note\n", {"name": "note", "template": "note.md"})

    assert out.splitlines() == ["name: note", "template: note.md"]


def test_a_dropped_key_takes_its_comment_with_it() -> None:
    """A comment explaining a field that no longer exists is worse than no comment:
    it reads as current."""
    out = _roundtrip("name: note\n# the old template\ntemplate: note.md\n", {"name": "note"})

    assert "template" not in out
    assert "the old template" not in out


def test_a_nested_mapping_keeps_its_comments() -> None:
    out = _roundtrip(
        "projection:\n  # which attachment feeds the body\n  source_role: source\n",
        {"projection": {"source_role": "raw"}},
    )

    assert "# which attachment feeds the body" in out
    assert "source_role: raw" in out


def test_a_list_entry_is_matched_by_identity_not_position() -> None:
    """The one place position is a bad proxy for sameness: inserting an entry at the
    top would otherwise shift every comment down one."""
    document = "fields:\n    -   name: title\n        # the human-facing name\n        type: string\n"

    out = _roundtrip(
        document,
        {"fields": [{"name": "slug", "type": "string"}, {"name": "title", "type": "string"}]},
    )

    lines = [line.strip() for line in out.splitlines()]
    assert lines.index("- name: slug") < lines.index("- name: title")
    # the comment travelled with `title` rather than staying at index 0
    assert lines.index("# the human-facing name") > lines.index("- name: title")


def test_a_list_without_an_identity_key_merges_by_position() -> None:
    out = _roundtrip("on_create_emit:\n    -   timeline  # always\n", {"on_create_emit": ["timeline", "readme"]})

    assert "# always" in out
    assert "readme" in out


def test_an_entry_the_payload_dropped_is_gone() -> None:
    out = _roundtrip(
        "fields:\n    -   name: title\n    -   name: legacy\n",
        {"fields": [{"name": "title"}]},
    )

    assert "legacy" not in out


@pytest.mark.parametrize("existing", [None, "not a mapping", [1, 2], 7])
def test_nothing_to_merge_into_returns_the_payload(existing: object) -> None:
    """A missing or non-mapping document has no structure worth preserving, so the
    payload stands on its own rather than being silently dropped into it."""
    payload = {"name": "note"}

    assert merge_into(existing, payload) == payload


def test_the_payload_is_never_mutated() -> None:
    payload = {"projection": {"source_role": "raw"}}

    merge_into(_YAML.load("projection:\n  source_role: source\n"), payload)

    assert payload == {"projection": {"source_role": "raw"}}
