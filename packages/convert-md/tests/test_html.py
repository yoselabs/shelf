"""convert_html: the in-memory HTML string door — by source kind, never raises."""

from __future__ import annotations

from convert_md import convert_html
from convert_md.base import ConversionResult

_ARTICLE = """
<html><head><title>Hello</title></head><body>
<article>
<h1>A Real Heading</h1>
<p>This is a paragraph with enough words to survive trafilatura's boilerplate
removal, so the extractor keeps it as the main content of the page.</p>
<p>A second paragraph, also with a comfortable amount of prose so the yield
heuristic does not discard the block as navigation chrome or a menu.</p>
</article>
</body></html>
"""


def test_returns_conversion_result() -> None:
    result = convert_html(_ARTICLE)
    assert isinstance(result, ConversionResult)
    assert "paragraph" in result.body_markdown
    assert result.engine.startswith("trafilatura@")


def test_url_is_accepted() -> None:
    result = convert_html(_ARTICLE, url="https://example.com/post")
    assert result.body_markdown
    assert result.fidelity in {"high", "partial"}


def test_empty_html_never_raises() -> None:
    result = convert_html("")
    assert isinstance(result, ConversionResult)
    assert result.body_markdown == ""
    assert result.fidelity == "failed"
    assert "all" in result.lost


def test_unextractable_markup_degrades_to_failed() -> None:
    # A bare fragment with no extractable article body — both engines yield nothing
    # meaningful; the door must return a result, not raise.
    result = convert_html("<div></div>")
    assert isinstance(result, ConversionResult)
    assert result.fidelity in {"failed", "partial", "high"}  # never an exception


def test_clean_source_kind_bypasses_the_web_extractor() -> None:
    # A clean fragment (e.g. rendered from docx): source_kind="clean" must render
    # it faithfully via html2text and NOT route through trafilatura, whose web
    # content-detection strips headings/tables when there is no page structure.
    fragment = "<h1>Heading</h1><table><tr><td>a</td><td>b</td></tr><tr><td>1</td><td>2</td></tr></table>"

    clean = convert_html(fragment, source_kind="clean")
    assert clean.engine.startswith("html2text@")  # never trafilatura
    assert "# Heading" in clean.body_markdown
    assert "|" in clean.body_markdown  # table survives as a table


# Realistic prose so trafilatura's yield heuristic keeps the block as main
# content (a single short sentence gets collapsed and the anchor lost — not a
# link-handling issue but a content-detection one).
_PARA = (
    "This is a substantial paragraph of real prose that comfortably survives "
    "trafilatura's boilerplate and yield heuristics, describing the subject in "
    "enough depth that the extractor treats it as genuine main content. "
)
_LINKED = f"""
<html><head><title>Widget</title></head><body><article>
<h1>The Widget Roundup</h1>
<p>{_PARA}</p>
<p>{_PARA} For the details, read the <a href="https://example.com/reviews">customer
reviews</a> which cover durability and value. {_PARA}</p>
<p>{_PARA}{_PARA}</p>
</article></body></html>
"""


def test_include_links_keeps_in_body_anchor() -> None:
    result = convert_html(_LINKED, url="https://example.com/p", include_links=True)
    assert "https://example.com/reviews" in result.body_markdown


def test_default_omits_link_target() -> None:
    result = convert_html(_LINKED, url="https://example.com/p")
    assert "https://example.com/reviews" not in result.body_markdown
    assert "customer" in result.body_markdown


# A discussion page: an original post plus a comment region. The markup shape is
# the real one trafilatura keys on (`<div class="comments">` with `id`-bearing
# comment nodes) rather than an invented one — a synthetic shape the extractor
# does not recognise would make these tests pass or fail for the wrong reason.
_COMMENT_BODY = (
    "The replies here carry the actual answer to the question, going into the "
    "specific failure mode and how the fix was verified, at enough length that "
    "the extractor treats the block as genuine content rather than chrome. "
)
_THREAD = f"""
<html><head><title>Thread</title></head><body><article>
<h1>Why does the widget stall under load?</h1>
<p>{_PARA} I have been unable to reproduce it locally and would appreciate
pointers on where to look next.</p>
</article>
<div class="comments">
  <div class="comment" id="comment-1"><p>{_COMMENT_BODY} The stall is the
  connection pool, not the widget.</p></div>
  <div class="comment" id="comment-2"><p>{_COMMENT_BODY} Confirmed by raising
  the pool ceiling, which removed it entirely.</p></div>
</div>
</body></html>
"""


def test_include_comments_keeps_the_discussion_region() -> None:
    """On a thread, the comments ARE the content — the default drops them.

    Without this knob a discussion page extracts to the original post alone: a
    question with no answer, returned as though it were the whole page. The
    caller cannot tell that from a thread that genuinely has no replies.
    """
    result = convert_html(_THREAD, url="https://example.com/t", include_comments=True)
    assert "connection pool" in result.body_markdown
    assert "pool ceiling" in result.body_markdown


def test_comments_are_dropped_by_default() -> None:
    """The article default is unchanged — comments stay boilerplate."""
    result = convert_html(_THREAD, url="https://example.com/t")
    assert "stall" in result.body_markdown, "the original post must survive"
    assert "connection pool" not in result.body_markdown


_TABLED = f"""
<html><head><title>Specs</title></head><body><article>
<h1>Widget Specifications</h1>
<p>{_PARA}</p>
<table><tr><th>Model</th><th>Weight</th></tr><tr><td>A1</td><td>420g</td></tr></table>
<p>{_PARA}{_PARA}</p>
</article></body></html>
"""


def test_tables_are_kept_by_default() -> None:
    result = convert_html(_TABLED, url="https://example.com/s")
    assert "420g" in result.body_markdown


def test_include_tables_false_drops_the_table() -> None:
    """A caller rendering its own rows from structured data opts out."""
    result = convert_html(_TABLED, url="https://example.com/s", include_tables=False)
    assert "420g" not in result.body_markdown
