"""A body fitted into a size budget: whole, or as much of its opening as fits plus an outline.

A reader with a fixed budget per call (an agent's tool result, a preview pane) cannot take
a 90K-character document whole, and a bare cut loses what follows. :meth:`Budget.view`
returns the body whole when it fits; otherwise:

- the **lead** — the opening a cut read shows: never a separator, a comment or a stray YAML
  block, never a bare title; up to a heading once a prose paragraph is in hand;
- grown by whole sections (a body with headings) or whole lines (one without), and into the
  first section's own lines, while it and the outline of the rest still fit — a view that
  stopped at its lead left most of the budget unused and cost the reader a second call;
- and an **outline** of what is not shown: heading sections, or ``lines:`` parts for text with
  no heading to cut at. An outline over its room folds its deepest level, and a single level
  that still does not fit becomes line parts.

Every id in an outline goes straight back to :meth:`Markdown.section`. Sizes are the
caller's: ``measure`` sizes text (characters by default; a JSON wire charges escapes), and
``row_cost`` sizes one outline row as the caller will render it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from any_markdown.sections import ATX_HEADING_RE, Section, clip, find, line_parts, outline

if TYPE_CHECKING:
    from collections.abc import Callable

_BREAK = re.compile(r"^ {0,3}([-*_])( *\1){2,} *$")
_COMMENT = re.compile(r"^\s*<!--.*-->\s*$")
#: A stray YAML block (``---`` / ``key: value`` lines / ``---``) left at the top of a body.
_YAML_BLOCK = re.compile(r"\A---[ \t]*\n(?:(?:[\w-]+:.*|[ \t-].*)\n)+---[ \t]*\n?\Z")


@dataclass(frozen=True)
class View:
    """What a budgeted read shows: a body, and the outline when that body is not all of it."""

    body: str
    outline: list[Section] | None
    truncated: bool


def _default_row_cost(measure: Callable[[str], int]) -> Callable[[Section], int]:
    return lambda row: measure(row.id) + measure(row.heading) + 8


@dataclass(frozen=True)
class Budget:
    """How a caller sizes text and outline rows, and how much a lead may take.

    ``lead`` is in ``measure`` units. ``row_cost`` defaults to the row's id and heading
    plus a few units of framing.
    """

    lead: int
    measure: Callable[[str], int] = len
    row_cost: Callable[[Section], int] | None = field(default=None)

    def row(self, row: Section) -> int:
        """What one outline row costs."""
        return (self.row_cost or _default_row_cost(self.measure))(row)

    def line_parts(self, text: str, part: int, *, base_line: int = 1) -> list[Section]:
        """``text`` as ``lines:`` parts of at most ``part``, ids counted from ``base_line``."""
        return line_parts(text, part, measure=self.measure, base_line=base_line)

    def hint(self, body: str, *, part: int, limit: int = 20) -> list[str]:
        """The first ``limit`` ids a reader can ask for: headings, else line parts."""
        rows = outline(body) or self.line_parts(body, part)
        return [r.id for r in rows[:limit]]

    def lead_of(self, body: str, budget: int | None = None) -> str:
        """The opening of ``body`` a cut read shows, within ``budget`` (default ``lead``).

        Blank lines, thematic breaks, HTML comments and a stray YAML block at the top are
        skipped. Paragraphs are then taken in order: up to a heading once a prose paragraph
        is in hand, never past the budget; a first prose paragraph over it is cut at a line,
        else a word. Empty only for a body with no text.
        """
        start, end = self._lead_span(body, self.lead if budget is None else budget)
        return body[start:end]

    def view(self, body: str, budget: int, *, part: int, room: int | None = None, base_line: int = 1) -> View:
        """``body`` whole when it fits ``budget``; otherwise its opening and an outline within ``room``.

        ``room`` (default ``budget``) bounds the shown text plus the outline. ``part`` is the
        size of a line part. ``base_line`` is where ``body`` starts in a larger document, so a
        part of a section names lines of the whole.
        """
        if self.measure(body) <= budget:
            return View(body=body, outline=None, truncated=False)
        room = budget if room is None else room
        lead_start, lead_end = self._lead_span(body, min(self.lead, room))
        shown = body[lead_start:lead_end]
        rows = outline(body)
        if rows and not body[: rows[0].start].strip():
            top = min(r.level for r in rows)
            tops = [r for r in rows if r.level == top]
            if len(tops) == 1 and tops[0].end == len(body):
                rows = rows[1:]  # the one container is the view itself
        filled = self._filled(body, lead_start, lead_end, rows, room, part, base_line)
        if filled is not None:
            return filled
        if not rows:
            return View(body=shown, outline=self.line_parts(body, part, base_line=base_line), truncated=True)
        head: list[Section] = []
        preamble = body[: rows[0].start]
        if body[lead_end : rows[0].start].strip() and _meaningful(preamble):
            head = self.line_parts(preamble, part, base_line=base_line)
        return View(body=shown, outline=self._fit(body, head, rows, room - self.measure(shown), part, base_line), truncated=True)

    def section_view(self, body: str, id_: str, budget: int, *, part: int, room: int | None = None) -> View | None:
        """Section ``id_`` of ``body`` through :meth:`view`, or ``None`` if there is none.

        Every outline id is the one the whole body gives that part: a line part counts
        lines of the body, and a heading keeps its body-wide dedupe (the second ``### Notes``
        is ``notes-2`` even when it is the first under the section).
        """
        found = find(body, id_)
        if found is None:
            return None
        start, end = found.start, found.end
        view = self.view(body[start:end], budget, room=room, part=part, base_line=body[:start].count("\n") + 1)
        if view.outline is None:
            return view
        body_ids = {row.start: row.id for row in outline(body)}
        rows = [replace(row, id=body_ids.get(start + row.start, row.id)) if row.level else row for row in view.outline]
        return View(body=view.body, outline=rows, truncated=view.truncated)

    # --- the lead -------------------------------------------------------------------------

    def _lead_span(self, body: str, budget: int) -> tuple[int, int]:
        blocks = _blocks(body)
        while blocks and (not _meaningful(text := body[blocks[0][0] : blocks[0][1]]) or _YAML_BLOCK.match(text)):
            blocks.pop(0)
        if not blocks or budget <= 0:
            return 0, 0
        start, end, prose = blocks[0][0], blocks[0][0], False
        for b_start, b_end in blocks:
            text = body[b_start:b_end]
            if prose and _is_heading_block(text):
                break
            if self.measure(body[start:b_end]) > budget:
                if not prose:
                    end = start + len(clip(body[start:b_end], budget, measure=self.measure))
                break
            end = b_end
            prose = prose or _has_prose(text)
        return start, end

    # --- filling the room past the lead ---------------------------------------------------

    def _filled(self, body: str, lead_start: int, lead_end: int, rows: list[Section], room: int, part: int, base_line: int) -> View | None:
        """The opening past the lead that fits ``room`` with the outline of the rest, or ``None``.

        With headings it ends where a section starts; without, at a line. Text the lead
        skipped at the top stays reachable as line parts in front."""
        skipped = body[:lead_start]
        head: list[Section] = self.line_parts(skipped, part, base_line=base_line) if _meaningful(skipped) else []
        room -= sum(self.row(r) for r in head)
        if rows:
            tail = [0] * (len(rows) + 1)  # tail[i]: what rows[i:] cost as outline rows
            for i in range(len(rows) - 1, -1, -1):
                tail[i] = tail[i + 1] + self.row(rows[i])
            best: int | None = None
            size, at = 0, lead_start
            for i, row in enumerate(rows):
                size += self.measure(body[at : row.start])  # an additive measure: sizes add
                at = row.start
                if row.start > lead_end and size + tail[i] <= room:
                    best = i
            if best is None:
                return None
            cut = rows[best].start
            grown = self._into_section(body, lead_start, cut, rows, best, room - tail[best + 1], part, base_line)
            if grown is not None:
                end, parts = grown
                return View(body=body[lead_start:end], outline=[*head, *parts, *rows[best + 1 :]], truncated=True)
            return View(body=body[lead_start:cut], outline=[*head, *rows[best:]], truncated=True)
        rest_cost = sum(self.row(r) for r in self.line_parts(body[lead_end:], part))
        end = lead_start + len(self._whole_lines(body[lead_start:], room - rest_cost))
        if end <= lead_end:
            return None
        rest = self.line_parts(body[end:], part, base_line=base_line + body[:end].count("\n"))
        shown = body[lead_start:end]
        if self.measure(shown) + sum(self.row(r) for r in rest) > room:
            return None
        return View(body=shown, outline=[*head, *rest], truncated=True)

    def _into_section(
        self, body: str, lead_start: int, cut: int, rows: list[Section], i: int, room: int, part: int, base_line: int
    ) -> tuple[int, list[Section]] | None:
        """Grow an opening that stops at ``rows[i]`` into that section's own lines, up to its
        first sub-heading. Returns where the opening ends and the line parts it leaves."""
        stop = rows[i + 1].start if i + 1 < len(rows) else rows[i].end
        own = body[cut:stop]
        opening = self.measure(body[lead_start:cut])
        taken = self._whole_lines(own, room - opening - sum(self.row(r) for r in self.line_parts(own, part)))
        if not taken.strip() or (ATX_HEADING_RE.match(taken.strip()) and "\n" not in taken.strip()):
            return None  # nothing past the heading line fits
        end = cut + len(taken)
        parts = self.line_parts(body[end:stop], part, base_line=base_line + body[:end].count("\n")) if end < stop else []
        if opening + self.measure(taken) + sum(self.row(r) for r in parts) > room:
            return None
        return end, parts

    def _whole_lines(self, text: str, budget: int) -> str:
        """The longest run of whole lines opening ``text`` within ``budget``."""
        taken, size = 0, 0
        for line in text.splitlines(keepends=True):
            size += self.measure(line)
            if size > budget:
                break
            taken += len(line)
        return text[:taken]

    def _fit(self, body: str, head: list[Section], rows: list[Section], room: int, part: int, base_line: int) -> list[Section]:
        """``head`` + ``rows`` within ``room``: fold the deepest level, then fall back to line parts."""

        def cost(rs: list[Section]) -> int:
            return sum(self.row(r) for r in [*head, *rs])

        while cost(rows) > room and len({r.level for r in rows}) > 1:
            deepest = max(r.level for r in rows)
            rows = [r for r in rows if r.level != deepest]
        if cost(rows) <= room:
            return [*head, *rows]
        return self.line_parts(body, part, base_line=base_line)


def _blocks(text: str) -> list[tuple[int, int]]:
    """``text``'s paragraphs as offsets: runs of non-blank lines, each ending past its last newline."""
    out: list[tuple[int, int]] = []
    start: int | None = None
    offset = 0
    for line in text.splitlines(keepends=True):
        if line.strip():
            if start is None:
                start = offset
        elif start is not None:
            out.append((start, offset))
            start = None
        offset += len(line)
    if start is not None:
        out.append((start, offset))
    return out


def _filler(line: str) -> bool:
    """A line that says nothing on its own: blank, a thematic break, an HTML comment."""
    return not line.strip() or bool(_BREAK.match(line)) or bool(_COMMENT.match(line))


def _meaningful(text: str) -> bool:
    return any(not _filler(line) for line in text.splitlines())


def _has_prose(text: str) -> bool:
    return any(not _filler(line) and not ATX_HEADING_RE.match(line) for line in text.splitlines())


def _is_heading_block(text: str) -> bool:
    return bool(ATX_HEADING_RE.match(text.splitlines()[0])) if text else False


__all__ = ["Budget", "View"]
