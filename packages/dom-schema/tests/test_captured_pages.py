"""The verification lane: real captured pages, not hand-written approximations.

This lane is the package's reason to be trusted. Both parsers `dom-schema` was
built from had green suites over hand-written fixtures at the moment they were
returning zero rows on the live site — a fixture authored from the same mental
model as the parser cannot fail when that model is wrong about the site, it can
only confirm the parser agrees with itself.

So every schema here runs against bytes fetched from the real site and committed
verbatim. Re-capture with:

    curl -A 'Mozilla/5.0' 'https://arxiv.org/list/cs.CL/recent' \
      > tests/fixtures/arxiv_list_cs_CL_recent.html

A failure here after a re-capture is the signal the package exists to produce:
the site changed, and the schema must follow. It is NOT a reason to relax the
assertion.
"""

from __future__ import annotations

from pathlib import Path

from dom_schema import Field, Schema, Yield, extract

_FIXTURES = Path(__file__).parent / "fixtures"

#: Captured 2026-07-28. The floor is deliberately well under the ~47 entries the
#: capture holds: this asserts the schema MATCHES, and pinning an exact count
#: would break on re-capture for a reason that is not a defect. "> 0" would pass
#: on one stray row, which is the vacuity this floor exists to prevent.
_ARXIV_MIN_ENTRIES = 20

_ARXIV = Schema(
    container="dl#articles",
    row="dt",
    pair_with="dd",
    fields={
        "id": Field(css="a[title='Abstract']", attr="href", required=True),
        "title": Field(css="div.list-title", strip_prefix="Title:", required=True),
        "authors": Field(css="div.list-authors", strip_prefix="Authors:"),
    },
)

#: Parsoid marks internal article links with `rel="mw:WikiLink"` and a RELATIVE
#: `./Target` href. The dead regex wanted `href="/wiki/X"` — the format Parsoid
#: had stopped serving.
_WIKILINKS = Schema(
    container="body",
    row="a[rel='mw:WikiLink']",
    fields={
        "href": Field(css=".", attr="href", required=True),
        "anchor": Field(css="."),
    },
)
_WIKI_MIN_LINKS = 10


def _fixture(name: str) -> str:
    path = _FIXTURES / name
    assert path.exists(), f"captured fixture missing: {path}. Re-capture it; do not hand-write one."
    return path.read_text(encoding="utf-8")


def test_arxiv_listing_extracts_its_entries() -> None:
    """The exact page that returned 0 entries in production on 2026-07-28."""
    got = extract(_fixture("arxiv_list_cs_CL_recent.html"), _ARXIV)

    assert got.verdict is Yield.OK, (
        f"verdict={got.verdict} on a captured arXiv listing. If this is ROT the site changed "
        "and the schema must follow — do not weaken the assertion."
    )
    assert len(got.rows) >= _ARXIV_MIN_ENTRIES, f"only {len(got.rows)} entries — schema is half-matching"
    first = got.rows[0]
    assert first["id"].startswith("/abs/"), first
    assert first["title"] and first["title"] != first["id"], "title fell back to the id — selector missed"
    assert not first["title"].startswith("Title:"), "the descriptor label leaked into the value"


def test_arxiv_listing_authors_are_present() -> None:
    """`authors` is the field the old regex lost entirely (0 of 3 patterns matched)."""
    got = extract(_fixture("arxiv_list_cs_CL_recent.html"), _ARXIV)

    with_authors = [r for r in got.rows if r.get("authors")]
    assert len(with_authors) >= _ARXIV_MIN_ENTRIES, f"only {len(with_authors)} rows carry authors"
    assert not with_authors[0]["authors"].startswith("Authors:")


def test_wikipedia_parsoid_wikilinks_are_found() -> None:
    """The relative-href shape a `href="/wiki/X"` regex returned 0 for."""
    got = extract(_fixture("wikipedia_parsoid_octopus_disambig.html"), _WIKILINKS)

    assert got.verdict is Yield.OK
    assert len(got.rows) >= _WIKI_MIN_LINKS, f"only {len(got.rows)} wikilinks"
    assert any(r["href"].startswith("./") for r in got.rows), (
        "no relative ./Target href found — this fixture is meant to carry the exact shape that broke the absolute-path regex"
    )


def test_a_stale_schema_over_a_real_page_reports_rot() -> None:
    """The whole point, against real bytes rather than a synthetic.

    This is the pre-fix arXiv selector: it assumes a container that the live
    page does not have. Against a real capture it must say ROT — the schema is
    wrong — and never EMPTY, which would blame the page.
    """
    stale = Schema(container="div#entries", row="div.entry", fields={"id": Field(css="a", attr="href")})
    got = extract(_fixture("arxiv_list_cs_CL_recent.html"), stale)

    assert got.verdict is Yield.ROT
    assert got.is_rot


def test_a_real_page_with_an_empty_container_is_empty_not_rot() -> None:
    """Emptiness must survive contact with a real document.

    Built by taking the captured page and emptying its container, so the
    surrounding document is genuine — only the rows are gone, which is what a
    quiet day on a listing site actually looks like.
    """
    html = _fixture("arxiv_list_cs_CL_recent.html")
    start = html.index("<dl id='articles'>") if "<dl id='articles'>" in html else html.index('<dl id="articles"')
    end = html.index("</dl>", start)
    emptied = html[:start] + "<dl id='articles'>" + html[end:]

    got = extract(emptied, _ARXIV)

    assert got.verdict is Yield.EMPTY, f"got {got.verdict} — an empty real page must not read as schema rot"
