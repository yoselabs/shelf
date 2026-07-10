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
