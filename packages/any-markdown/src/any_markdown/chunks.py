"""A markdown document cut into overlapping retrieval windows that know where they sit.

Heading-aware: the text is split where a line opens with an ATX ``#`` run, then each span
is packed into overlapping windows of ``size`` characters, so a long section becomes several
chunks. Each chunk records the 1-based line it starts on (a ``file:line`` hit), the headings
above it (a context header), and the id of the section it sits in — one
:meth:`~any_markdown.Markdown.section` takes back: the innermost heading's slug, else
``lines:A-B``, and inside a line longer than ``part`` the characters it holds,
``lines:N:A-B``, so a hit deep in a one-line transcript opens there, not at the line's start.

The window split uses a looser heading rule than :mod:`any_markdown.sections` (any ``#``
run followed by whitespace, fences not consulted); the section ids come from
:attr:`~any_markdown.Markdown.sections`. Both are kept as they were promoted, because
chunk boundaries and ids are stored by consumers' search indexes.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from typing import TYPE_CHECKING

from any_markdown._lines import line_starts

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Sequence

    from any_markdown.sections import Section

_SPLIT_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)
#: The most a character can cost under any measure ``chunk`` accepts: a JSON ``\\uXXXX`` escape.
_MAX_UNIT = 6


@dataclass(frozen=True)
class Chunk:
    """One retrieval window: where it starts, its text, the section it sits in, the headings above it."""

    line: int
    text: str
    #: The id of the section holding the chunk's start, as ``Markdown.section`` takes it.
    section: str | None = None
    #: The headings above the chunk, outermost first.
    headings: tuple[str, ...] = ()


def chunk(
    text: str,
    sections: Sequence[Section],
    *,
    size: int = 1100,
    overlap: int = 150,
    part: int | None = None,
    measure: Callable[[str], int] = len,
) -> list[Chunk]:
    """``text`` cut into heading-aware windows of ``size`` characters, ``overlap`` shared.

    ``sections`` is ``text``'s outline. A line over ``part`` (by ``measure``, which may charge
    at most six units a character) gives its chunks character ids; ``None`` means no line is
    too long.
    """
    if not text.strip():
        return []
    bounds = [m.start() for m in _SPLIT_RE.finditer(text)]
    spans: list[tuple[int, int]] = []
    if not bounds or bounds[0] != 0:
        spans.append((0, bounds[0] if bounds else len(text)))
    for i, b in enumerate(bounds):
        spans.append((b, bounds[i + 1] if i + 1 < len(bounds) else len(text)))
    starts = line_starts(text)
    long = _long_lines(text, starts, part, measure) if part is not None else set()
    out: list[Chunk] = []
    for s, e in spans:
        out.extend(_windows(text[s:e], s, starts, sections, long, size, overlap))
    return out


def _long_lines(text: str, starts: list[int], part: int, measure: Callable[[str], int]) -> set[int]:
    """The lines (1-based) over ``part``: their chunks name the characters they hold."""
    ends = [*starts[1:], len(text)]
    spans = enumerate(zip(starts, ends, strict=True))
    return {i + 1 for i, (a, b) in spans if b - a > part // _MAX_UNIT and measure(text[a:b]) > part}


def _windows(
    segment: str, base: int, starts: list[int], sections: Sequence[Section], long: Collection[int], size: int, overlap: int
) -> list[Chunk]:
    chunks: list[Chunk] = []
    start = 0
    n = len(segment)
    while start < n:
        end = min(start + size, n)
        piece = segment[start:end].strip()
        if piece:
            line = bisect_right(starts, base + start)  # 1-based: line starts at or before here
            around = [s for s in sections if s.start <= base + start < s.end]
            last = line + piece.count("\n")
            if line in long and last == line:
                a = base + start - starts[line - 1]
                section = f"lines:{line}:{a}-{a + end - start}"
            else:
                section = around[-1].id if around else f"lines:{line}-{last}"
            chunks.append(Chunk(line=line, text=piece, section=section, headings=tuple(s.heading for s in around)))
        if end == n:
            break
        start = end - overlap
    return chunks


__all__ = ["Chunk", "chunk"]
