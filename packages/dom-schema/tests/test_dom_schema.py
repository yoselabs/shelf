"""The three-way verdict is the package. Everything here exists to pin it.

A bare `list[Row]` conflates "the page is empty" with "the schema stopped
matching". Both come back as zero rows, so callers report "nothing here" for
both, and a rotted scraper answers that indefinitely with nothing to notice.
These tests pin the separation, in both directions.
"""

from __future__ import annotations

from dom_schema import Field, Schema, Yield, extract

_LISTING = Schema(
    container="dl#articles",
    row="dt",
    pair_with="dd",
    fields={
        "id": Field(css="a[title='Abstract']", attr="href", required=True),
        "title": Field(css="div.list-title", strip_prefix="Title:", required=True),
        "authors": Field(css="div.list-authors", strip_prefix="Authors:"),
    },
)


def _entry(i: int) -> str:
    return (
        f"<dt><a href='/abs/{i}' title='Abstract'>arXiv:{i}</a></dt>"
        f"<dd><div class='list-title mathjax'><span class='descriptor'>Title:</span> Paper {i}</div>"
        f"<div class='list-authors'><span class='descriptor'>Authors:</span> Author {i}</div></dd>"
    )


def _page(n: int) -> str:
    return f"<html><body><dl id='articles'>{''.join(_entry(i) for i in range(n))}</dl></body></html>"


def test_ok_extracts_named_fields_across_the_dt_dd_pair() -> None:
    got = extract(_page(3), _LISTING)

    assert got.verdict is Yield.OK
    assert len(got.rows) == 3
    assert got.rows[0] == {"id": "/abs/0", "title": "Paper 0", "authors": "Author 0"}


def test_empty_page_is_reported_as_empty_not_rot() -> None:
    """The container is there and holds nothing. A fact about the PAGE."""
    got = extract("<html><body><dl id='articles'></dl></body></html>", _LISTING)

    assert got.verdict is Yield.EMPTY
    assert not got.is_rot, "an empty listing must never be blamed on the schema"


def test_changed_markup_is_reported_as_rot_not_empty() -> None:
    """The container is gone. A fact about the SCHEMA — never about the page."""
    got = extract("<html><body><section class='articles'><dt>x</dt></section></body></html>", _LISTING)

    assert got.verdict is Yield.ROT
    assert got.is_rot
    assert got.rows == ()


def test_half_rot_is_rot_when_every_field_selector_misses() -> None:
    """Container right, field selectors wrong. Blaming the page would be a lie."""
    rows = "<dt><a href='/abs/1'>1</a></dt><dd><span>Paper</span></dd>" * 3
    got = extract(f"<html><body><dl id='articles'>{rows}</dl></body></html>", _LISTING)

    assert got.verdict is Yield.ROT, "structural rows with no extractable fields is schema failure"
    assert got.missing["title"] == 3


def test_partial_field_rot_is_counted_not_swallowed() -> None:
    """A schema can match its container and still be half-broken."""
    good = _entry(0)
    bare = "<dt><a href='/abs/9' title='Abstract'>arXiv:9</a></dt><dd><div class='list-title'>Title: Paper 9</div></dd>"
    got = extract(f"<html><body><dl id='articles'>{good}{bare}</dl></body></html>", _LISTING)

    assert got.verdict is Yield.OK
    assert len(got.rows) == 2
    assert "authors" not in got.rows[1]


def test_quote_style_and_whitespace_are_not_failure_modes() -> None:
    """The rot this package exists for was a regex requiring `href="`.

    arXiv serves single quotes and `<a href ="…">`; the wikipedia parser died on
    `href="./X"` vs `href="/wiki/X"`. A DOM parse is indifferent to all of it, and
    this test is the standing evidence for choosing one over a tolerant regex.
    """
    messy = (
        "<html><body><dl id = 'articles'>\n"
        "  <dt>\n    <a href =\"/abs/7\" title='Abstract'>\n      arXiv:7\n    </a>\n  </dt>\n"
        "  <dd><div class='list-title mathjax'><span class='descriptor'>Title:</span>\n"
        "      Paper 7\n  </div></dd>\n</dl></body></html>"
    )
    got = extract(messy, _LISTING)

    assert got.verdict is Yield.OK
    assert got.rows[0]["id"] == "/abs/7"
    assert got.rows[0]["title"] == "Paper 7"


def test_flat_schema_without_pairing_still_works() -> None:
    """`pair_with` is opt-in; the common single-element row must stay simple."""
    schema = Schema(
        container="ul.results",
        row="li",
        fields={"href": Field(css="a", attr="href"), "label": Field(css="a")},
    )
    html = "<html><body><ul class='results'><li><a href='/a'>Alpha</a></li><li><a href='/b'>Beta</a></li></ul></body></html>"
    got = extract(html, schema)

    assert got.verdict is Yield.OK
    assert [r["label"] for r in got.rows] == ["Alpha", "Beta"]


def test_extraction_is_falsy_on_both_failure_verdicts() -> None:
    """`if not got:` must not silently accept EMPTY as a success."""
    assert extract(_page(2), _LISTING)
    assert not extract("<html><body><dl id='articles'></dl></body></html>", _LISTING)
    assert not extract("<html><body></body></html>", _LISTING)
