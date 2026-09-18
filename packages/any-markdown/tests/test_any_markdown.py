"""What the document says, and what it only appears to say."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from any_markdown import Markdown, WikiLink, anchor_of, parse_one

if TYPE_CHECKING:
    from pathlib import Path


def _anchors(text: str) -> list[str]:
    return [link.anchor for link in Markdown(text).wikilinks]


# --- what counts as a link -------------------------------------------------


def test_prose_links_are_read_in_document_order() -> None:
    assert _anchors("See [[research/152]] then [[Robin Vale]].") == ["research/152", "Robin Vale"]


def test_a_link_inside_an_inline_code_span_is_an_example() -> None:
    assert _anchors("The convention is `[[me]]`, as in [[Robin Vale]].") == ["Robin Vale"]


def test_a_link_inside_a_fenced_block_is_an_example() -> None:
    assert _anchors("a [[one]]\n\n```\n[[two]]\n```\n\nb [[three]]") == ["one", "three"]


def test_a_link_inside_an_indented_code_block_is_an_example() -> None:
    # Four-space indent is CommonMark code. A marker-line regex misses this entirely.
    assert _anchors("text:\n\n    [[indented]]\n\nafter [[real]]") == ["real"]


def test_an_indented_continuation_inside_a_list_is_prose() -> None:
    # The naive repair for the case above — "four spaces means code" — breaks this,
    # which is ordinary wrapped list text and commonly carries real links.
    assert _anchors("- an item that wraps\n    and continues to [[Robin Vale]]\n") == ["Robin Vale"]


def test_a_short_closing_fence_does_not_close_a_longer_one() -> None:
    # ``` cannot close ````, so everything between the outer pair stays code.
    assert _anchors("````\n[[one]]\n```\n[[two]]\n````\n") == []


def test_a_fence_with_an_info_string_is_still_a_fence() -> None:
    assert _anchors("~~~python\n[[one]]\n~~~\n\n[[two]]") == ["two"]


def test_backticks_inside_a_wider_code_span_do_not_end_it() -> None:
    assert _anchors("``a ` b [[one]]`` then [[two]]") == ["two"]


def test_a_lone_backtick_in_prose_opens_nothing() -> None:
    assert _anchors("it's the 90`s, see [[Robin Vale]]") == ["Robin Vale"]


def test_an_unclosed_fence_runs_to_the_end() -> None:
    assert _anchors("before [[one]]\n\n```\n[[two]]\n[[three]]\n") == ["one"]


# --- what a link carries ---------------------------------------------------


def test_a_link_reports_its_display_name_and_position() -> None:
    (link,) = Markdown("x [[a2kay/136|a2kay]] y").wikilinks
    assert (link.anchor, link.name, link.display) == ("a2kay/136", "a2kay", "a2kay")
    assert link.text == "[[a2kay/136|a2kay]]"
    assert "x [[a2kay/136|a2kay]] y"[slice(*link.span)] == link.text


def test_a_missing_display_name_is_none_and_an_empty_one_is_empty() -> None:
    absent, empty = Markdown("[[a]] [[b|]]").wikilinks
    assert absent.name is None
    assert empty.name == ""
    assert absent.display == "a"  # falls back to the anchor
    assert empty.display == "b"


def test_an_anchor_is_stripped_but_the_text_is_verbatim() -> None:
    (link,) = Markdown("[[  spaced  ]]").wikilinks
    assert link.anchor == "spaced"
    assert link.text == "[[  spaced  ]]"


def test_a_link_is_hashable_so_callers_can_deduplicate() -> None:
    assert len({WikiLink("a", None, (0, 5), "[[a]]"), WikiLink("a", None, (0, 5), "[[a]]")}) == 1


# --- rewriting -------------------------------------------------------------


def test_rewriting_touches_prose_links_only() -> None:
    body = "Write `[[a|old]]` to link.\n\n```\n[[a|old]]\n```\n\nLive: [[a|old]]\n"
    out = Markdown(body).replace_wikilinks(lambda link: f"[[{link.anchor}|new]]")
    assert out.text.count("[[a|old]]") == 2  # both examples verbatim
    assert "Live: [[a|new]]" in out.text


def test_returning_the_links_own_text_is_the_no_op() -> None:
    body = "a [[one]] b `[[two]]` c\n"
    assert Markdown(body).replace_wikilinks(lambda link: link.text).text == body


def test_rewriting_returns_a_new_document_and_leaves_the_original() -> None:
    doc = Markdown("[[a]]")
    assert doc.replace_wikilinks(lambda _: "[[b]]").text == "[[b]]"
    assert doc.text == "[[a]]"


def test_a_rewritten_document_can_be_rewritten_again() -> None:
    doc = Markdown("[[a]] and `[[skip]]`")
    once = doc.replace_wikilinks(lambda link: f"[[{link.anchor}x]]")
    assert once.replace_wikilinks(lambda link: f"[[{link.anchor}y]]").text == "[[axy]] and `[[skip]]`"


def test_a_document_with_no_links_is_returned_unchanged() -> None:
    body = "Nothing to see.\n"
    assert Markdown(body).replace_wikilinks(lambda _: "[[x]]").text == body


# --- the document itself ---------------------------------------------------


def test_from_path_defers_the_read_until_something_is_asked(tmp_path: Path) -> None:
    note = tmp_path / "n.md"
    note.write_text("[[a]]", encoding="utf-8")
    doc = Markdown.from_path(note)
    note.write_text("[[b]]", encoding="utf-8")  # still unread
    assert [link.anchor for link in doc.wikilinks] == ["b"]
    assert doc.path == note


def test_a_document_built_from_text_has_no_path() -> None:
    assert Markdown("[[a]]").path is None


def test_code_spans_and_is_code_agree_with_what_was_excluded() -> None:
    doc = Markdown("a `[[x]]` b")
    position = doc.text.index("[[x]]")
    assert doc.is_code(position)
    assert not doc.is_code(0)
    assert any(start <= position < end for start, end in doc.code_spans)


def test_the_token_stream_is_reachable_as_an_escape_hatch() -> None:
    assert [t.type for t in Markdown("# h\n").tokens][:1] == ["heading_open"]


def test_repr_names_the_path_when_there_is_one(tmp_path: Path) -> None:
    note = tmp_path / "n.md"
    note.write_text("[[a]]", encoding="utf-8")
    assert str(note) in repr(Markdown.from_path(note))


# --- one authored value, not a document ------------------------------------


@pytest.mark.parametrize(
    ("value", "anchor"),
    [("[[Robin Vale]]", "Robin Vale"), ("[[research/152|R152]]", "research/152"), ("136", "136"), ("  spaced  ", "spaced"), (136, "136")],
)
def test_anchor_of_unwraps_or_passes_through(value: object, anchor: str) -> None:
    assert anchor_of(value) == anchor


def test_parse_one_accepts_only_a_whole_wikilink() -> None:
    assert parse_one("  [[a|B]]  ") == WikiLink(anchor="a", name="B", span=(0, 7), text="[[a|B]]")
    assert parse_one("prose with [[a]] inside") is None
    assert parse_one("136") is None
