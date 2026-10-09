"""parse / dump / read / write — comments kept, one error type, atomic write."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from any_frontmatter import Document, FrontmatterError, dump, parse, read, write

if TYPE_CHECKING:
    from pathlib import Path

SAMPLE = """---
id: P136
type: project
title: a2kay
tags:
  - kb
  - mcp
---
# a2kay

body line one
body line two
"""

COMMENTED = """---
# what this entity is for
id: P136
kind: Project  # inline note the user wrote
tags:
  - kb
---
body
"""


def test_parse_splits_frontmatter_and_body() -> None:
    doc = parse(SAMPLE)
    assert doc.frontmatter["id"] == "P136"
    assert doc.frontmatter["tags"] == ["kb", "mcp"]
    assert doc.body.startswith("# a2kay")


def test_no_fence_is_empty_frontmatter() -> None:
    doc = parse("just body\nno fence\n")
    assert doc.frontmatter == {}
    assert doc.body == "just body\nno fence\n"


@pytest.mark.parametrize("text", ["---\n---\nbody\n", "---\nnull\n---\nbody\n", "---\n   \n---\nbody\n"])
def test_blank_or_null_frontmatter_is_empty(text: str) -> None:
    assert parse(text) == Document(frontmatter={}, body="body\n")


def test_unclosed_fence_raises() -> None:
    with pytest.raises(FrontmatterError, match="unclosed"):
        parse("---\nid: x\nno closing fence ever\n")


def test_non_mapping_raises() -> None:
    with pytest.raises(FrontmatterError, match="mapping"):
        parse("---\n- not a mapping\n---\nbody\n")


@pytest.mark.parametrize(
    "fm",
    ["title: [unclosed\n", "a:\n\tb: 1\n", "a: 1\na: 2\n", "a: *nope\n", "a: b: c\n", "a: 'oops\n"],
)
def test_malformed_yaml_is_a_frontmatter_error(fm: str) -> None:
    with pytest.raises(FrontmatterError):
        parse(f"---\n{fm}---\nbody\n")


def test_the_error_keeps_the_parsers_position_and_cause() -> None:
    from ruamel.yaml.error import YAMLError  # noqa: PLC0415 — the cause's type is the assertion

    with pytest.raises(FrontmatterError) as caught:
        parse("---\ntitle: [unclosed\n---\nbody\n")
    assert "line" in str(caught.value).lower()
    assert isinstance(caught.value.__cause__, YAMLError)


def test_dump_round_trips() -> None:
    doc = parse(SAMPLE)
    again = parse(dump(doc))
    assert again.frontmatter == doc.frontmatter
    assert again.body == doc.body


def test_dump_omits_the_fence_with_no_frontmatter() -> None:
    assert dump(Document(frontmatter={}, body="just body\n")) == "just body\n"


def test_a_plain_dict_dumps() -> None:
    assert "id: P1" in dump(Document(frontmatter={"id": "P1"}, body="hi\n"))


def test_comments_survive_a_round_trip_and_a_changed_value() -> None:
    assert "# inline note the user wrote" in dump(parse(COMMENTED))
    doc = parse(COMMENTED)
    doc.frontmatter["kind"] = "Research"
    out = dump(doc)
    assert "# what this entity is for" in out
    assert "kind: Research" in out


def test_a_long_value_with_double_spaces_round_trips() -> None:
    """A wrapped plain scalar folds its line break into one space."""
    path = "projects/estimation/AirCare  Pitch Deck  January  2026-1.pdf"
    doc = Document(frontmatter={"title": "AirCare  Pitch Deck", "extra": {"source": path}}, body="x\n")
    again = parse(dump(doc))
    assert again.frontmatter["extra"]["source"] == path
    assert again.frontmatter["title"] == "AirCare  Pitch Deck"


def test_a_plain_long_value_keeps_its_style() -> None:
    assert '"' not in dump(Document(frontmatter={"summary": ("word " * 30).strip()}, body=""))


def test_write_creates_parents_and_leaves_no_temp_file(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deep" / "entity.md"
    write(target, Document(frontmatter={"id": "x"}, body="hello\n"))
    assert read(target) == Document(frontmatter={"id": "x"}, body="hello\n")
    assert list(target.parent.glob(".entity.md.*.tmp")) == []


def test_a_failed_write_keeps_the_old_file(tmp_path: Path) -> None:
    target = tmp_path / "e.md"
    write(target, Document(frontmatter={"id": "x"}, body="old\n"))

    class Unwritable:
        def __str__(self) -> str:
            msg = "cannot render"
            raise RuntimeError(msg)

    with pytest.raises(Exception):  # noqa: B017 — whatever the dumper raises, the file survives
        write(target, Document(frontmatter={"id": Unwritable()}, body="new\n"))
    assert read(target).body == "old\n"
    assert list(tmp_path.glob(".e.md.*.tmp")) == []


def test_with_frontmatter_keeps_comments_and_replaces_keys() -> None:
    doc = parse(COMMENTED)
    out = doc.with_frontmatter({"id": "P136", "kind": "Research"}, body="new\n")
    text = dump(out)
    assert "# what this entity is for" in text
    assert "kind: Research" in text
    assert "tags" not in out.frontmatter
    assert out.body == "new\n"
    assert doc.with_frontmatter(dict(doc.frontmatter)).body == "body\n"


def test_a_failed_dump_does_not_empty_the_next_one() -> None:
    """ruamel keeps a half-written document in a reused emitter; the next dump wrote ``{}``."""

    class Unwritable:
        pass

    with pytest.raises(Exception):  # noqa: B017 — ruamel's RepresenterError
        dump(Document(frontmatter={"id": Unwritable()}, body="x\n"))
    assert dump(Document(frontmatter={"a": 1}, body="x\n")) == "---\na: 1\n---\nx\n"


def test_the_double_space_rule_stays_inside_the_package() -> None:
    from io import StringIO  # noqa: PLC0415

    from ruamel.yaml import YAML  # noqa: PLC0415

    buf = StringIO()
    YAML(typ="rt").dump({"t": "a  b"}, buf)
    assert '"' not in buf.getvalue()


def test_round_trip_yaml_carries_the_double_space_rule() -> None:
    from io import StringIO  # noqa: PLC0415

    from any_frontmatter import round_trip_yaml  # noqa: PLC0415

    buf = StringIO()
    round_trip_yaml().dump({"t": "a  b", "u": "plain"}, buf)
    assert buf.getvalue() == 't: "a  b"\nu: plain\n'
