"""A document cut into addressable sections, and text with no heading cut into line parts.

Moved from a2kay's ``core/sections.py`` tests with the code they cover; the ids and parts are
byte-for-byte what a2kay handed out before the move.
"""

from __future__ import annotations

import json

import pytest
from any_markdown import ATX_HEADING_RE, Markdown, Section, clip, line_parts, slug


def _ids(text: str) -> list[str]:
    return [s.id for s in Markdown(text).sections]


def _text(text: str, id_: str) -> str | None:
    found = Markdown(text).section(id_)
    return None if found is None else text[found.start : found.end]


def _wire(text: str) -> int:
    """A byte measure, as a consumer that budgets JSON on the wire would pass it."""
    return len(json.dumps(text, ensure_ascii=False).encode()) - 2


# --- heading sections ----------------------------------------------------------------


def test_slugs_are_github_style_and_deduped_in_document_order() -> None:
    body = "# Plan\n\n## Scope & Goals\n\nx\n\n## Scope & Goals\n\ny\n\n### Ничего страшного 🚀\n\nz\n"
    assert _ids(body) == ["plan", "scope--goals", "scope--goals-2", "ничего-страшного-"]


def test_a_heading_of_only_punctuation_slugs_to_section() -> None:
    assert slug("!!!") == "section"
    assert _ids("## ???\n\n## ???\n") == ["section", "section-2"]


def test_a_section_is_its_heading_and_subtree_to_the_next_peer() -> None:
    body = "lead\n\n## A\n\na1\n\n### A.1\n\na2\n\n## B\n\nb\n"
    assert _text(body, "a") == "## A\n\na1\n\n### A.1\n\na2\n\n"
    assert _text(body, "a1") == "### A.1\n\na2\n\n"
    assert _text(body, "b") == "## B\n\nb\n"


def test_sections_report_level_and_chars() -> None:
    body = "## A\n\naaaa\n\n## B\n\nb\n"
    rows = Markdown(body).sections
    assert [(s.heading, s.level, s.chars) for s in rows] == [("A", 2, len("## A\n\naaaa\n\n")), ("B", 2, len("## B\n\nb\n"))]


def test_a_closing_hash_run_is_not_part_of_the_heading() -> None:
    assert [s.heading for s in Markdown("## Title ##\n\n### Plain\n").sections] == ["Title", "Plain"]


def test_a_hash_line_inside_a_fence_is_not_a_heading() -> None:
    body = "## Real\n\n```sh\n# a shell comment\n```\n\n~~~\n## not this\n~~~\n\n## Also real\n"
    assert _ids(body) == ["real", "also-real"]


def test_unknown_id_is_none() -> None:
    assert Markdown("## A\n\nx\n").section("nope") is None


def test_the_heading_rule_is_exposed_for_a_caller_that_reads_lines() -> None:
    m = ATX_HEADING_RE.match("### Notes ###")
    assert m is not None
    assert (m.group(1), m.group(2)) == ("###", "Notes")
    assert ATX_HEADING_RE.match("#nospace") is None


# --- line parts ------------------------------------------------------------------------


def test_heading_less_text_splits_into_line_parts_at_blank_lines() -> None:
    para = "word " * 30  # 150 chars a paragraph
    body = "\n\n".join(para for _ in range(20)) + "\n"
    parts = line_parts(body, 400)
    assert len(parts) > 1
    assert all(p.id.startswith("lines:") and p.level == 0 and p.heading == p.id for p in parts)
    assert all(len(_text(body, p.id) or "") <= 400 for p in parts)
    assert "".join(_text(body, p.id) or "" for p in parts) == body


def test_lines_id_round_trips_any_range() -> None:
    body = "one\ntwo\nthree\nfour\n"
    assert _text(body, "lines:2-3") == "two\nthree\n"
    assert _text(body, "lines:3-9") is None  # past the end is not a section
    assert _text(body, "lines:0-1") is None


def test_a_lines_section_carries_its_offsets() -> None:
    assert Markdown("one\ntwo\nthree\n").section("lines:2-3") == Section(
        id="lines:2-3", heading="lines:2-3", level=0, chars=10, start=4, end=14
    )


@pytest.mark.parametrize("bad", ["lines:", "lines:a-b", "lines:3-2"])
def test_malformed_lines_id_is_none(bad: str) -> None:
    assert Markdown("a\nb\nc\n").section(bad) is None


def test_part_ids_count_from_base_line() -> None:
    parts = line_parts("a\n\nb\n", 3, base_line=5)
    assert [p.id for p in parts] == ["lines:5-6", "lines:7-7"]


#: A raw machine transcript: one line of ~60K chars under a heading, the fact deep inside.
_RAW = "## Transcript\n\n" + "слово " * 6000 + "больше 20 штук " + "слово " * 4000 + "\n"


def test_parts_of_a_long_line_cover_it_at_word_breaks() -> None:
    line = _RAW.splitlines(keepends=True)[2]
    parts = line_parts(line, 11_000, measure=_wire, base_line=3)
    assert len(parts) > 1
    assert all(p.id.startswith("lines:3:") for p in parts)
    assert "".join(_text(_RAW, p.id) or "" for p in parts) == line
    assert all((_text(_RAW, p.id) or "").endswith((" ", "\n")) for p in parts)
    assert all(_wire(_text(_RAW, p.id) or "") <= 11_000 for p in parts)


def test_the_measure_decides_where_parts_cut() -> None:
    """Cyrillic is two UTF-8 bytes a character: a byte measure cuts twice as often."""
    line = "слово " * 1000 + "\n"
    assert len(line_parts(line, 1000, measure=_wire)) > len(line_parts(line, 1000))


def test_a_word_longer_than_a_part_is_cut_where_the_budget_ends() -> None:
    line = "short " + "x" * 25 + " tail\n"
    parts = line_parts(line, 10)
    assert "".join(line[p.start : p.end] for p in parts) == line
    assert all(p.chars <= 10 for p in parts)


def test_a_part_of_a_line_outside_the_line_is_none() -> None:
    assert Markdown("short\n").section("lines:1:0-99") is None
    assert Markdown("short\n").section("lines:2:0-1") is None
    assert Markdown("short\n").section("lines:1:3-3") is None


# --- clip --------------------------------------------------------------------------------


def test_clip_cuts_after_a_line_else_a_word() -> None:
    assert clip("one\ntwo\nthree\n", 9) == "one\ntwo\n"
    assert clip("alpha beta gamma", 12) == "alpha beta "


def test_clip_of_one_word_over_the_budget_is_never_empty() -> None:
    assert clip("x" * 100, 8) == "xx"
