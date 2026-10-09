"""Budget — a body fitted into a size budget: whole, or its opening plus an outline.

Measured as a JSON wire would charge: UTF-8 bytes inside a JSON string, and an outline row as
its JSON object. Any measure works; this one makes escapes and non-ASCII matter.
"""

from __future__ import annotations

import json

from any_markdown import Budget, Markdown, Section, View

READ = 12_000
LEAD = 1_500
PART = 11_000


def wire(text: str) -> int:
    return len(json.dumps(text, ensure_ascii=False).encode()) - 2


def row(r: Section) -> int:
    return 41 + wire(r.id) + wire(r.heading) + len(str(r.level)) + len(str(r.chars))


W = Budget(lead=LEAD, measure=wire, row_cost=row)


def section(body: str, id_: str) -> str | None:
    found = Markdown(body).section(id_)
    return None if found is None else body[found.start : found.end]


def budgeted(body: str, *, budget: int = READ, room: int | None = None, part: int = PART, base_line: int = 1) -> View:
    return W.view(body, budget, room=room, part=part, base_line=base_line)


def budgeted_section(body: str, id_: str) -> View | None:
    return W.section_view(body, id_, READ, part=PART)


def lead(body: str, *, budget: int = LEAD) -> str:
    return W.lead_of(body, budget)


def test_the_lead_stops_at_the_first_heading() -> None:
    assert lead("lead\n\n## A\n\na1\n") == "lead\n"


def test_line_parts_are_measured_in_wire_bytes() -> None:
    line = "слово " * 1000 + "\n"  # two UTF-8 bytes a letter: over 6,000 chars is over 11,000 bytes
    parts = W.line_parts(line, 5_000)
    assert len(parts) == 3
    assert all(wire(line[p.start : p.end]) <= 5_000 for p in parts)


def test_budgeted_view_of_a_short_body_is_the_whole_body() -> None:
    view = budgeted("## A\n\nshort\n", budget=100)
    assert view.body == "## A\n\nshort\n"
    assert view.outline is None
    assert view.truncated is False


def test_budgeted_view_of_a_long_sectioned_body_is_its_opening_plus_outline() -> None:
    body = "intro line\n" + "".join(f"\n## Part {k}\n\n{'w' * 300}\n" for k in range(10))
    view = budgeted(body, budget=1000)
    assert view.truncated is True
    assert view.body.startswith("intro line\n\n## Part 0\n")  # the lead, then whole sections
    assert view.outline is not None
    first = int(view.outline[0].id.removeprefix("part-"))
    assert f"## Part {first - 1}\n" in view.body
    assert [s.id for s in view.outline] == [f"part-{k}" for k in range(first, 10)]


def test_budgeted_view_of_an_h1_first_body_descends_into_the_title() -> None:
    """A 90K document is `# title` then 40 `##`: no lead before the first heading.

    The first heading's subtree is the whole document, so the outline is the `##` sections
    under it; the lead is the title, the first heading and its first paragraph, never a bare title.
    """
    body = "# Household move\n" + "".join(f"\n## Section {k}\n\n{'w' * 300}\n" for k in range(10))
    view = budgeted(body, budget=1000)
    assert view.truncated is True
    assert view.body.startswith("# Household move\n\n## Section 0\n\n" + "w" * 300 + "\n")
    assert view.outline is not None
    assert view.outline[0].id.startswith("section-")
    assert all(s.level == 2 for s in view.outline)


def test_budgeted_view_of_a_long_heading_less_body_falls_back_to_line_parts() -> None:
    body = "\n\n".join("word " * 30 for _ in range(40)) + "\n"
    view = budgeted(body, budget=1000)
    assert view.truncated is True
    assert view.outline is not None
    assert all(p.id.startswith("lines:") for p in view.outline)
    assert view.body.startswith("word ")
    assert wire(view.body) + sum(row(r) for r in view.outline) <= 1000
    assert view.body + "".join(section(body, p.id) or "" for p in view.outline) == body


def test_budgeted_section_over_budget_recurses() -> None:
    body = "## Big\n\n" + "".join(f"### Sub {k}\n\n{'w' * 300}\n\n" for k in range(10)) + "## Small\n\nx\n"
    big = section(body, "big")
    assert big is not None
    view = budgeted(big, budget=1000)
    assert view.truncated is True
    assert view.body.startswith("## Big\n\n### Sub 0\n\nwww")
    assert view.outline is not None
    assert 0 < len(view.outline) < 10
    assert all(s.level == 3 for s in view.outline)


def test_line_part_ids_are_absolute_in_the_whole_body() -> None:
    """A part of a section names lines of the entity's body, so `section=` can fetch it."""
    filler = "\n\n".join("word " * 30 for _ in range(30))
    body = "## Head\n\nshort\n\n## Call\n\n" + filler + "\n"
    call = section(body, "call")
    assert call is not None
    offset = body.index(call)
    view = budgeted(call, budget=1000, base_line=body[:offset].count("\n") + 1)
    assert view.outline is not None
    first = view.outline[0]
    assert first.id.startswith("lines:5-")
    part = section(body, first.id)
    assert part is not None
    assert part.startswith(view.body)


# --- wire bytes, the lead, an outline that fits -------------------


def test_the_lead_skips_a_separator_preamble() -> None:
    body = "---\n\n<!-- imported -->\n\n# Title\n\n## Scope\n\nWhat this is about.\n\n## Next\n\nmore\n"
    assert lead(body) == "# Title\n\n## Scope\n\nWhat this is about.\n"


def test_the_lead_of_a_body_with_no_text_is_empty() -> None:
    assert lead("---\n\n\n") == ""


def test_the_lead_takes_paragraphs_up_to_its_budget() -> None:
    para = "word " * 40  # 200 bytes
    body = "\n\n".join(para for _ in range(20)) + "\n"
    got = lead(body, budget=700)
    assert got.count("word ") == 120  # three paragraphs; a fourth would pass 700
    assert body.startswith(got)


def test_the_lead_of_one_giant_table_is_cut_at_a_row() -> None:
    rows = "".join(f"| row {k} | {'cell ' * 20} |\n" for k in range(300))
    body = "| name | text |\n| --- | --- |\n" + rows
    got = lead(body)
    assert got.startswith("| name | text |\n| --- | --- |\n| row 0 |")
    assert got.endswith("|\n")
    assert wire(got) <= LEAD


def test_the_lead_of_one_long_line_is_cut_at_a_word() -> None:
    body = "word " * 2000
    got = lead(body)
    assert got
    assert wire(got) <= LEAD
    assert got.rstrip().endswith("word")


def test_a_preamble_longer_than_the_lead_is_listed_as_line_parts() -> None:
    preamble = "\n\n".join("intro " * 50 for _ in range(10)) + "\n"
    body = preamble + "".join(f"\n## Part {k}\n\n{'w' * 300}\n" for k in range(10))
    view = budgeted(body, budget=1000, room=2500)  # the preamble alone is over the room
    assert view.outline is not None
    head = [r for r in view.outline if r.level == 0]
    assert head
    assert head[0].id.startswith("lines:1-")
    shown = "".join(section(body, r.id) or "" for r in head)
    assert shown == body[: body.index("## Part 0")]
    assert [r.id for r in view.outline if r.level][:1] == ["part-0"]


def test_an_outline_over_its_room_folds_the_deepest_level() -> None:
    body = "".join(f"## Part {k}\n\n" + "".join(f"### Sub {k}.{j}\n\n{'w' * 100}\n\n" for j in range(10)) for k in range(10))
    tight = budgeted(body, budget=1000, room=1500)
    assert tight.outline is not None
    assert {r.level for r in tight.outline} == {2}
    assert sum(row(r) for r in tight.outline) + wire(tight.body) <= 1500


def test_one_level_over_its_room_becomes_line_parts_of_the_whole_body() -> None:
    body = "".join(f"## A heading long enough to cost bytes {k}\n\n{'w' * 50}\n\n" for k in range(300))
    view = budgeted(body, budget=1000, room=3000, part=5000)
    assert view.outline is not None
    assert all(r.level == 0 for r in view.outline)
    assert "".join(section(body, r.id) or "" for r in view.outline) == body


def test_the_lead_skips_a_stray_yaml_block_at_the_top() -> None:
    body = "---\nkind: synthesis\nsource: k\n---\n\n# Title\n\nThe point.\n"
    assert lead(body) == "# Title\n\nThe point.\n"


def test_a_leading_rule_over_prose_is_not_taken_for_yaml() -> None:
    body = "---\n\nPlain opening words.\n\n---\n\nmore\n"
    assert lead(body).startswith("Plain opening words.")


def test_the_lead_shrinks_to_the_room_left() -> None:
    body = "\n\n".join("word " * 40 for _ in range(200)) + "\n"
    view = budgeted(body, budget=100, room=500, part=5000)
    assert wire(view.body) <= 500
    assert view.body


# --- a cut read fills its budget ------------------------------


def _big(n: int = 40, per: int = 1000) -> str:
    return "# Big\n" + "".join(f"\n## Part {k}\n\n{'word ' * (per // 5)}\n" for k in range(n))


def _covered(body: str, view: View) -> str:
    """What the view's body and its outline ids give back, in order."""
    assert view.outline is not None
    return view.body + "".join(section(body, row.id) or "" for row in view.outline)


def test_a_cut_body_shows_whole_leading_sections_up_to_the_budget() -> None:
    body = _big()
    view = budgeted(body, budget=12_000)
    assert view.truncated is True
    assert view.outline is not None
    shown = [k for k in range(40) if f"## Part {k}\n" in view.body]
    assert shown == list(range(len(shown)))
    assert len(shown) >= 8, "the room is used, not left at a 1,500-byte lead"
    assert view.outline[0].id == f"part-{len(shown)}", "the outline lists what the body does not show"
    assert wire(view.body) + sum(row(r) for r in view.outline) <= 12_000


def test_what_a_filled_view_leaves_out_is_reachable_by_its_outline() -> None:
    body = _big()
    view = budgeted(body, budget=12_000)
    assert _covered(body, view).strip() == body.strip()


def test_a_heading_less_body_fills_with_lines_and_outlines_the_rest() -> None:
    body = "\n\n".join(f"Turn {k}: " + "word " * 60 for k in range(200)) + "\n"
    view = budgeted(body, budget=12_000)
    assert view.outline is not None
    assert wire(view.body) > 8_000
    assert wire(view.body) + sum(row(r) for r in view.outline) <= 12_000
    assert all(r.id.startswith("lines:") for r in view.outline)
    assert view.body + "".join(section(body, r.id) or "" for r in view.outline) == body


def test_a_body_under_one_big_heading_fills_with_its_lines() -> None:
    """A call is often `## Transcript` over everything: whole sections alone showed 850 bytes of 19 KB."""
    body = "Summary line.\n\n## Transcript\n\n" + "".join(f"[{k:02d}:00] me: " + "word " * 40 + "\n\n" for k in range(200))
    view = budgeted(body, budget=12_000)
    assert view.outline is not None
    assert view.body.startswith("Summary line.\n\n## Transcript\n\n[00:00]")
    assert wire(view.body) > 8_000
    assert wire(view.body) + sum(row(r) for r in view.outline) <= 12_000
    assert view.body + "".join(section(body, r.id) or "" for r in view.outline) == body


# --- a line longer than a part -------------------------------------------

#: A raw machine transcript: one line of ~60K chars under a heading, the fact deep inside.
_RAW = "## Transcript\n\n" + "слово " * 6000 + "больше 20 штук " + "слово " * 4000 + "\n"


def _walk(body: str, id_: str) -> str:
    """Every part a reader reaches from ``id_`` by following outline ids it has not read."""
    seen: set[str] = set()
    read: list[str] = []
    todo = [id_]
    while todo:
        cur = todo.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        view = budgeted_section(body, cur)
        assert view is not None, cur
        read.append(view.body)
        todo += [r.id for r in view.outline or []]
    return "".join(read)


def test_a_line_longer_than_a_part_is_read_to_its_end() -> None:
    assert "больше 20 штук" in _walk(_RAW, "transcript")


def test_each_part_of_a_long_line_comes_back_whole() -> None:
    view = budgeted_section(_RAW, "lines:3-3")
    assert view is not None and view.outline
    for row in view.outline:
        part = budgeted_section(_RAW, row.id)
        assert part is not None and not part.truncated, row.id
        assert wire(part.body) <= PART


def test_the_default_measure_is_characters_and_rows_cost_their_text() -> None:
    plain = Budget(lead=20)
    body = "".join(f"## Part {k}\n\n{'w' * 50}\n\n" for k in range(20))
    view = plain.view(body, 300, part=200)
    assert view.truncated is True
    assert view.outline is not None
    assert len(view.body) + sum(plain.row(r) for r in view.outline) <= 300
    assert plain.row(view.outline[0]) == len(view.outline[0].id) + len(view.outline[0].heading) + 8


def test_hint_lists_headings_else_line_parts() -> None:
    assert W.hint("## A\n\nx\n\n## B\n\ny\n", part=PART) == ["a", "b"]
    assert W.hint("one\n\ntwo\n", part=4)[0].startswith("lines:")
    assert len(W.hint("".join(f"## H{k}\n" for k in range(30)), part=PART, limit=5)) == 5


def test_an_unknown_section_is_none() -> None:
    assert W.section_view("## A\n\nx\n", "nope", READ, part=PART) is None


def test_a_section_that_fits_comes_back_whole() -> None:
    view = W.section_view("## A\n\nx\n\n## B\n\ny\n", "b", READ, part=PART)
    assert view == View(body="## B\n\ny\n", outline=None, truncated=False)
