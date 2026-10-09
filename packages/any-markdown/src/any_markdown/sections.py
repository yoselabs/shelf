"""A markdown document as addressable sections, and the line parts of text with none.

- A **section** is an ATX heading plus its subtree, up to the next heading of the same or a
  higher level. Its id is the heading's GitHub-style :func:`slug`, deduped ``-2``, ``-3`` in
  document order, so it survives inserting a section elsewhere.
- A **line part** (``lines:A-B``, 1-based, inclusive) is the fallback for text with no
  heading to cut at — transcripts, dumps, one big table. A line too long for one part is cut
  at word breaks into ``lines:N:A-B``: characters ``A`` to ``B`` of line ``N``.

The heading scan is a line scanner, not the CommonMark block grammar: a line is a heading
when it matches :data:`ATX_HEADING_RE` outside a ```` ``` ```` / ``~~~`` fence. That is
deliberate — ids are handed to clients and stored, so they must not move when a parser's
reading of an edge case does (a trailing ``#`` run, a heading inside an HTML block).

How big a part may be is the caller's measure: characters by default, or whatever its wire
charges (UTF-8 bytes, JSON-escaped bytes) — pass ``measure=``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

ATX_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
"""One ATX heading line, without its newline: group 1 the ``#`` run, group 2 the text."""

_FENCE = re.compile(r"^[ \t]{0,3}(```|~~~)")
#: ``lines:A-B``, or ``lines:N:A-B`` — characters ``A`` to ``B`` (0-based, ``B`` excluded) of line ``N``.
_LINES_ID = re.compile(r"^lines:(\d+)(?:-(\d+)|:(\d+)-(\d+))$")


@dataclass(frozen=True)
class Section:
    """One addressable part of a text: a heading's subtree (``level`` 1-6), or a line part (``level`` 0).

    ``start`` and ``end`` are offsets into the text it was cut from, so the section's text
    is ``text[start:end]``; ``chars`` is that length. A line part's ``heading`` is its id.
    """

    id: str
    heading: str
    level: int
    chars: int
    start: int
    end: int


def slug(text: str) -> str:
    """GitHub's anchor for a heading: lower case, punctuation dropped, spaces to hyphens."""
    out = re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")
    return out or "section"


def outline(text: str) -> list[Section]:
    """Every heading section of ``text``, in document order, ids deduped."""
    heads: list[tuple[int, int, str]] = []  # (offset, level, heading)
    offset = 0
    fenced = False
    for line in text.splitlines(keepends=True):
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced and (m := ATX_HEADING_RE.match(line.rstrip("\r\n"))):
            heads.append((offset, len(m.group(1)), m.group(2)))
        offset += len(line)
    used: set[str] = set()
    rows: list[Section] = []
    for i, (start, level, heading) in enumerate(heads):
        end = next((s for s, lvl, _ in heads[i + 1 :] if lvl <= level), len(text))
        base = candidate = slug(heading)
        n = 1
        while candidate in used:
            n += 1
            candidate = f"{base}-{n}"
        used.add(candidate)
        rows.append(Section(id=candidate, heading=heading, level=level, chars=end - start, start=start, end=end))
    return rows


def find(text: str, id_: str, *, rows: Sequence[Section] | None = None) -> Section | None:
    """Section ``id_`` of ``text`` — a heading slug or a ``lines:`` id — or ``None`` if there is none.

    ``rows`` is ``text``'s :func:`outline` when the caller already holds it.
    """
    if id_.startswith("lines:"):
        return _lines(text, id_)
    return next((row for row in (outline(text) if rows is None else rows) if row.id == id_), None)


def line_parts(text: str, budget: int, *, measure: Callable[[str], int] = len, base_line: int = 1) -> list[Section]:
    """``text`` cut into line ranges of at most ``budget`` (by ``measure``), at blank lines where it can.

    A single line over the budget is cut at word breaks into parts of its own characters.
    Ids count lines from ``base_line``, so a part of a section can name lines of the whole
    document. The parts cover ``text`` exactly, in order.
    """
    lines = text.splitlines(keepends=True)
    sizes = [measure(x) for x in lines]
    parts: list[Section] = []
    first, size, offset = 0, 0, 0  # index of the part's first line, its size, its offset
    last_blank: int | None = None  # index just past the part's last blank line
    for i, line in enumerate(lines):
        if sizes[i] > budget:
            if first < i:
                parts.append(_part(lines, first, i, offset, base_line))
                offset += sum(len(x) for x in lines[first:i])
            parts += _line_pieces(line, budget, base_line + i, offset, measure)
            offset += len(line)
            first, size, last_blank = i + 1, 0, None
            continue
        while size and size + sizes[i] > budget:
            cut = last_blank if last_blank is not None and first < last_blank <= i else i
            parts.append(_part(lines, first, cut, offset, base_line))
            offset += sum(len(x) for x in lines[first:cut])
            first, size, last_blank = cut, sum(sizes[cut:i]), None
        size += sizes[i]
        if not line.strip():
            last_blank = i + 1
    if first < len(lines):
        parts.append(_part(lines, first, len(lines), offset, base_line))
    return parts


def clip(text: str, budget: int, *, measure: Callable[[str], int] = len) -> str:
    """The longest opening of ``text`` within ``budget``, cut after a line, else after a word.

    Never empty for non-empty text: a first word over the budget is cut at ``budget // 4``
    characters, which fits any measure that charges at most four units a character.
    """
    taken = ""
    for line in text.splitlines(keepends=True):
        if measure(taken + line) > budget:
            break
        taken += line
    if taken:
        return taken
    for word in re.split(r"(?<=\s)", text):
        if measure(taken + word) > budget:
            break
        taken += word
    return taken or text[: max(budget // 4, 1)]


def _part(lines: list[str], first: int, stop: int, offset: int, base_line: int) -> Section:
    chars = sum(len(x) for x in lines[first:stop])
    ident = f"lines:{base_line + first}-{base_line + stop - 1}"
    return Section(id=ident, heading=ident, level=0, chars=chars, start=offset, end=offset + chars)


def _line_pieces(line: str, budget: int, n: int, offset: int, measure: Callable[[str], int]) -> list[Section]:
    """``line`` (line ``n``, at ``offset``) cut at word breaks into parts of at most ``budget``."""
    out: list[Section] = []
    start, at, size = 0, 0, 0
    for word in re.split(r"(?<=\s)", line):
        rest, cost = word, measure(word)
        if size and size + cost > budget:
            out.append(_piece(n, start, at, offset))
            start, size = at, 0
        while cost > budget:  # one word longer than a part: cut it where the budget ends
            head = len(clip(rest, budget, measure=measure))
            out.append(_piece(n, at, at + head, offset))
            at, rest = at + head, rest[head:]
            start, cost = at, measure(rest)
        at += len(rest)
        size += cost
    if start < len(line):
        out.append(_piece(n, start, len(line), offset))
    return out


def _piece(n: int, a: int, b: int, offset: int) -> Section:
    ident = f"lines:{n}:{a}-{b}"
    return Section(id=ident, heading=ident, level=0, chars=b - a, start=offset + a, end=offset + b)


def _lines(text: str, id_: str) -> Section | None:
    m = _LINES_ID.match(id_)
    if m is None:
        return None
    lines = text.splitlines(keepends=True)
    if m.group(3) is not None:  # characters of one line
        n, a, b = int(m.group(1)), int(m.group(3)), int(m.group(4))
        if not (1 <= n <= len(lines) and 0 <= a < b <= len(lines[n - 1])):
            return None
        start = sum(len(x) for x in lines[: n - 1])
        return Section(id=id_, heading=id_, level=0, chars=b - a, start=start + a, end=start + b)
    a, b = int(m.group(1)), int(m.group(2))
    if not 1 <= a <= b <= len(lines):
        return None
    start = sum(len(x) for x in lines[: a - 1])
    chars = sum(len(x) for x in lines[a - 1 : b])
    return Section(id=id_, heading=id_, level=0, chars=chars, start=start, end=start + chars)


__all__ = ["ATX_HEADING_RE", "Section", "clip", "find", "line_parts", "outline", "slug"]
