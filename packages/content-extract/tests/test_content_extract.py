"""content-extract — extraction + metadata unit tests.

Ported from a2web's ``test_extract`` and ``test_metadata`` suites. The body Markdown
now comes from ``convert_md.convert_html``; everything else (metadata, headings,
role-classified links) is unchanged.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest
from content_extract import extract_markdown, parse_metadata

_FIX = Path(__file__).parent / "fixtures"
_BLOG = _FIX / "blog.html"


# --------------------------------------------------------------------- #
# Extraction — markdown, metadata, date
# --------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_extract_blog_markdown() -> None:
    html = _BLOG.read_text()
    result = await extract_markdown(html, "https://example.org/post/x")
    assert result.title is not None
    assert "adaptive" in result.title.lower()
    assert len(result.content_md) > 500
    assert any("Why one fetch" in h.text for h in result.headings)
    assert any("github.com/example/a2web" in link.href for link in result.links)


@pytest.mark.asyncio
async def test_extract_returns_published_date() -> None:
    html = _BLOG.read_text()
    result = await extract_markdown(html, "https://example.org/post/x")
    assert result.published == datetime.date(2026, 4, 1)


@pytest.mark.asyncio
async def test_extract_no_date_yields_none() -> None:
    result = await extract_markdown("<html><body><p>no date</p></body></html>", "https://x/y")
    assert result.published is None


# --------------------------------------------------------------------- #
# Link role classification
# --------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_link_in_nav_classified_nav() -> None:
    html = """<html><body>
        <nav><a href="https://x/home">Home</a></nav>
    </body></html>"""
    result = await extract_markdown(html, "https://x/")
    assert len(result.links) == 1
    assert result.links[0].role == "nav"


@pytest.mark.asyncio
async def test_link_in_footer_classified_footer() -> None:
    html = """<html><body>
        <footer><a href="https://x/about">About</a></footer>
    </body></html>"""
    result = await extract_markdown(html, "https://x/")
    assert result.links[0].role == "footer"


@pytest.mark.asyncio
async def test_link_in_article_classified_primary() -> None:
    html = """<html><body>
        <article><p>Read <a href="https://x/more">more here</a>.</p></article>
    </body></html>"""
    result = await extract_markdown(html, "https://x/")
    assert result.links[0].role == "primary"


@pytest.mark.asyncio
async def test_link_in_header_classified_meta() -> None:
    html = """<html><body>
        <header><a href="https://x/branding">Brand</a></header>
    </body></html>"""
    result = await extract_markdown(html, "https://x/")
    assert result.links[0].role == "meta"


@pytest.mark.asyncio
async def test_link_with_role_navigation_attr_classified_nav() -> None:
    """ARIA role='navigation' on a <div> should classify nav, not just <nav>."""
    html = """<html><body>
        <div role="navigation"><a href="https://x/menu">Menu</a></div>
    </body></html>"""
    result = await extract_markdown(html, "https://x/")
    assert result.links[0].role == "nav"


@pytest.mark.asyncio
async def test_link_unclassified_defaults_primary() -> None:
    """Bare anchor with no semantic ancestor falls back to 'primary'."""
    html = """<html><body>
        <div><a href="https://x/y">Anchor</a></div>
    </body></html>"""
    result = await extract_markdown(html, "https://x/")
    assert result.links[0].role == "primary"


@pytest.mark.asyncio
async def test_link_nested_inner_role_wins() -> None:
    """Closest ancestor wins — anchor in <nav> inside <article> is nav."""
    html = """<html><body>
        <article><nav><a href="https://x/inner">Inner</a></nav></article>
    </body></html>"""
    result = await extract_markdown(html, "https://x/")
    assert result.links[0].role == "nav"


# --------------------------------------------------------------------- #
# Metadata — OG, Twitter, JSON-LD
# --------------------------------------------------------------------- #


def test_og_extraction() -> None:
    html = _BLOG.read_text()
    meta = parse_metadata(html)
    assert meta["og.type"] == "article"
    assert meta["og.image"] == "https://example.org/cover.jpg"
    assert meta["og.title"].startswith("How adaptive web fetching")


def test_twitter_extraction() -> None:
    html = _BLOG.read_text()
    meta = parse_metadata(html)
    assert meta["twitter.card"] == "summary_large_image"
    assert meta["twitter.site"] == "@example"


def test_jsonld_extraction() -> None:
    html = _BLOG.read_text()
    meta = parse_metadata(html)
    assert meta["jsonld[0].@type"] == "Article"
    assert meta["jsonld[0].datePublished"] == "2026-04-01T09:00:00Z"


def test_no_metadata_returns_empty_dict() -> None:
    meta = parse_metadata("<html><body><p>plain</p></body></html>")
    assert meta == {}


def test_malformed_jsonld_is_swallowed() -> None:
    html = """
    <html><head>
    <script type="application/ld+json">{ this is not json</script>
    </head><body></body></html>
    """
    meta = parse_metadata(html)
    assert all(not k.startswith("jsonld[") for k in meta)
