"""dom-schema boundary types.

Pure dataclasses; package-owned. Domain-independent — no consumer types leak in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Yield(StrEnum):
    """Why an extraction produced the number of rows it produced.

    The whole point of the package. A bare `list[Row]` cannot distinguish an
    empty page from a schema that has stopped matching, so callers default to
    treating both as "nothing here" — which is silent, and which is how a
    selector can rot for months behind a green test suite.
    """

    #: Container matched, rows extracted.
    OK = "ok"
    #: Container matched and held no rows. The page really is empty; this is an
    #: observation ABOUT the page and a caller may act on it.
    EMPTY = "empty"
    #: The container itself did not match. The page is not the shape this schema
    #: describes — it was redesigned, replaced, or served as something else. This
    #: is an observation about the SCHEMA, never about the page, and a caller
    #: must not report it as "nothing found".
    ROT = "rot"


@dataclass(slots=True, frozen=True)
class Field:
    """One named value to pull out of a row.

    `css` is resolved within the row element. `attr` reads an attribute
    (`href`, `datetime`); omitted, the field takes the element's text with
    whitespace collapsed. `strip_prefix` removes a fixed label some sites weld
    onto the value (`"Title:"`), which is otherwise every consumer's first
    hand-rolled `.replace`.
    """

    css: str
    attr: str | None = None
    strip_prefix: str | None = None
    required: bool = False


@dataclass(slots=True, frozen=True)
class Schema:
    """A declared shape for one page type.

    Two levels, and the second is what makes rot separable from emptiness:
    `container` locates the region, `row` locates the repeated units inside it.
    A schema with only a flat selector cannot tell you which of the two failed.

    `pair_with` handles definition-list shapes, where one logical row spans TWO
    sibling elements (`<dt>` + `<dd>`). The rows come from `row`; each is paired
    positionally with the matching element from `pair_with`, and fields may be
    read from either half.
    """

    container: str
    row: str
    fields: dict[str, Field]
    pair_with: str | None = None


@dataclass(slots=True, frozen=True)
class Extraction:
    """The result: rows plus WHY there are that many of them."""

    verdict: Yield
    rows: tuple[dict[str, str], ...] = ()
    #: Fields declared `required` that were absent from at least one row, with a
    #: count. A schema can match its container and still be half-rotted; this is
    #: that middle ground, reported rather than swallowed.
    missing: dict[str, int] = field(default_factory=dict)

    def __bool__(self) -> bool:
        """True only on `OK`. `EMPTY` and `ROT` are both falsy, deliberately."""
        return self.verdict is Yield.OK

    @property
    def is_rot(self) -> bool:
        """The schema stopped describing the page. Never a fact about the page."""
        return self.verdict is Yield.ROT
