"""Read the links out of a markdown document without re-deriving where its code is.

``[[anchor|name]]`` wikilinks (MediaWiki's spelling, Obsidian's popularization) are not
CommonMark, so no markdown library extracts them — but deciding which of them are *real*
requires the whole CommonMark block grammar, because a wikilink inside a code block or a
code span is someone writing *about* the syntax, not linking. That split is why apps
hand-roll this: the grammar is one regex, and the part that must be correct is the part a
library already does.

So the block scan is delegated to ``markdown-it-py`` (fenced blocks, indented blocks, HTML
blocks — including the cases a regex gets wrong: a four-space block, a short closing fence,
an indented continuation inside a list that only *looks* like code), and inline code spans
are found by scanning the regions the parser left as prose.

    doc = Markdown.from_path(note)      # body read on first use, then kept
    for link in doc.wikilinks:          # code-span examples never appear here
        resolve(link.anchor)
    doc.replace_wikilinks(retitle).text  # same exclusion on the way out
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any

from markdown_it import MarkdownIt

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]*))?\]\]")
"""The ``[[anchor|name]]`` grammar. Exposed because a caller sometimes holds one
authored value rather than a document — see :func:`parse_one` and :func:`anchor_of`,
which are usually what that caller wants instead."""

_INLINE_CODE_RE = re.compile(r"(`+)(?:.|\n)*?\1")
_BLOCK_CODE_TOKENS = frozenset({"code_block", "fence", "html_block"})


@dataclass(frozen=True, slots=True)
class WikiLink:
    """One ``[[anchor|name]]`` occurrence, with where it was found.

    ``anchor`` is what resolves (stripped); ``name`` is the optional display half and is
    ``None`` when the link was written without one — absent and empty are different, since
    ``[[a|]]`` is an authored empty name. ``span`` indexes the document text, so a caller
    can report a position or splice without searching for the link again.
    """

    anchor: str
    name: str | None
    span: tuple[int, int]
    text: str

    @property
    def display(self) -> str:
        """What a reader sees — the display name when there is one, else the anchor."""
        return self.name or self.anchor


def parse_one(value: str) -> WikiLink | None:
    """The link ``value`` *is*, or ``None`` if it merely contains one.

    For a single authored value (a frontmatter field, a CLI argument) where "the whole
    string is one wikilink" and "some prose mentioning a wikilink" must be told apart.
    """
    text = value.strip()
    match = WIKILINK_RE.fullmatch(text)
    return None if match is None else _link(match, offset=0)


def anchor_of(value: object) -> str:
    """The resolvable anchor of an authored value, wrapped or bare.

    ``"[[Robin Vale]]"`` and ``"Robin Vale"`` both give ``"Robin Vale"``, so a caller
    never resolves against literal brackets. A non-string is coerced, because frontmatter
    hands back whatever YAML decided a value was.
    """
    text = str(value).strip()
    match = WIKILINK_RE.search(text)
    return match.group(1).strip() if match else text


def _link(match: re.Match[str], *, offset: int) -> WikiLink:
    return WikiLink(
        anchor=match.group(1).strip(),
        name=match.group(2),
        span=(match.start() + offset, match.end() + offset),
        text=match.group(0),
    )


class Markdown:
    """A markdown document that knows where its own code is.

    Construct from text, or :meth:`from_path` to defer the read until something is asked
    of it. Everything derived — the parse, the code regions, the links — is computed once
    and kept, so walking a vault costs one parse per file rather than one per question.

    Frontmatter is not this type's business: hand it the body if the caller has its own
    frontmatter reader, or the whole file if a leading ``---`` block is acceptable as the
    CommonMark it parses as.
    """

    def __init__(self, text: str | None = None, *, path: Path | str | None = None, encoding: str = "utf-8") -> None:
        if text is None and path is None:
            msg = "a Markdown needs either text or a path"
            raise ValueError(msg)
        self._text = text
        self._path = Path(path) if path is not None else None
        self._encoding = encoding

    @classmethod
    def from_path(cls, path: Path | str, *, encoding: str = "utf-8") -> Markdown:
        """A document backed by ``path``, read on first use rather than now."""
        return cls(path=path, encoding=encoding)

    @property
    def path(self) -> Path | None:
        """Where this came from, when it came from a file."""
        return self._path

    @property
    def text(self) -> str:
        """The document source."""
        if self._text is None:
            assert self._path is not None  # noqa: S101 — guaranteed by __init__
            self._text = self._path.read_text(encoding=self._encoding)
        return self._text

    @cached_property
    def tokens(self) -> list[Any]:
        """The markdown-it token stream — the escape hatch, for questions this type has
        no method for yet. Held, never inherited from."""
        return MarkdownIt("commonmark").parse(self.text)

    @cached_property
    def code_spans(self) -> Sequence[tuple[int, int]]:
        """Half-open ``(start, end)`` character ranges covering every code region.

        Block-level regions come from the CommonMark parse; inline spans are then found
        in what the parser left as prose, so a fence's contents can never be re-scanned
        for backticks.
        """
        text = self.text
        starts = _line_starts(text)
        ranges: list[tuple[int, int]] = []
        for token in _walk(self.tokens):
            if token.type in _BLOCK_CODE_TOKENS and token.map:
                first, last = token.map
                ranges.append((starts[first], starts[last] if last < len(starts) else len(text)))
        ranges.sort()
        for match in _INLINE_CODE_RE.finditer(text):
            if not any(start <= match.start() < end for start, end in ranges):
                ranges.append((match.start(), match.end()))
        ranges.sort()
        return tuple(ranges)

    def is_code(self, position: int) -> bool:
        """Whether ``position`` in :attr:`text` falls inside code."""
        return any(start <= position < end for start, end in self.code_spans)

    @cached_property
    def wikilinks(self) -> Sequence[WikiLink]:
        """Every ``[[link]]`` the document actually makes, in document order.

        A link inside a code block or a code span is an example of the syntax and is not
        here — which is the whole reason to hold this type rather than run the regex.
        """
        return tuple(_link(m, offset=0) for m in WIKILINK_RE.finditer(self.text) if not self.is_code(m.start()))

    def replace_wikilinks(self, repl: Callable[[WikiLink], str]) -> Markdown:
        """A new document with each real link passed through ``repl``.

        The write-side twin of :attr:`wikilinks`, sharing its exclusion, so a rewrite can
        never reach into a code span and corrupt a note that documents the link syntax.
        Returning the link's own :attr:`~WikiLink.text` is the no-op.
        """
        out: list[str] = []
        last = 0
        for link in self.wikilinks:
            start, end = link.span
            out.append(self.text[last:start])
            out.append(repl(link))
            last = end
        out.append(self.text[last:])
        return Markdown("".join(out))

    def __repr__(self) -> str:
        where = f" path={self._path}" if self._path is not None else ""
        return f"<Markdown{where} chars={len(self.text)}>"


def _walk(tokens: list[Any]) -> list[Any]:
    out: list[Any] = []
    for token in tokens:
        out.append(token)
        if token.children:
            out.extend(_walk(token.children))
    return out


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for index, char in enumerate(text):
        if char == "\n":
            starts.append(index + 1)
    return starts


__all__ = ["WIKILINK_RE", "Markdown", "WikiLink", "anchor_of", "parse_one"]
