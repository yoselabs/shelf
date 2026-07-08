"""In-memory HTML → Markdown — the string-door companion to ``convert(path)``.

A fetched web page is already in memory and carries a source URL for relative-link
resolution, so it never touches disk. :func:`convert_html` runs trafilatura first
(best boilerplate removal) with an html2text fallback, and follows ``convert()``'s
never-raises contract: a ``failed``-fidelity empty result when both engines give up.

The consumer keeps its own presentation policy (how a low-fidelity result surfaces);
this is the conversion mechanism only.
"""

from __future__ import annotations

from convert_md.base import ConversionResult
from convert_md.engines import _result, _ver


def convert_html(html: str, *, url: str | None = None) -> ConversionResult:
    """Convert an in-memory HTML string to Markdown, url-aware for link resolution.

    Args:
        html: The raw HTML document text.
        url: The page's source URL, passed to trafilatura so relative links resolve
            against it. Optional — omit for a fragment with no base.

    Returns:
        A graded :class:`ConversionResult`. Never raises: if trafilatura and
        html2text both extract nothing, a ``failed``-fidelity empty result is
        returned so the caller can still proceed.
    """
    source_size = len(html.encode("utf-8", errors="replace"))
    markdown = _extract_trafilatura(html, url=url)
    if markdown.strip():
        return _result(markdown, f"trafilatura@{_ver('trafilatura')}", source_size)
    markdown = _extract_html2text(html)
    if markdown.strip():
        return _result(markdown, f"html2text@{_ver('html2text')}", source_size)
    return ConversionResult(
        body_markdown="",
        engine=f"trafilatura@{_ver('trafilatura')}",
        fidelity="failed",
        lost=["all"],
        warnings=["conversion_failed"],
    )


def _extract_trafilatura(html: str, *, url: str | None) -> str:
    """Run trafilatura on the HTML string (boilerplate-stripped, tables kept)."""
    try:
        import trafilatura  # noqa: PLC0415 — lazy import keeps package import cheap
    except ImportError:  # pragma: no cover
        return ""
    return (
        trafilatura.extract(
            html,
            url=url,
            output_format="markdown",
            include_tables=True,
            include_comments=False,
        )
        or ""
    )


def _extract_html2text(html: str) -> str:
    """Fallback: html2text with unbounded line width."""
    try:
        import html2text  # noqa: PLC0415 — lazy import keeps package import cheap
    except ImportError:  # pragma: no cover
        return ""
    converter = html2text.HTML2Text()
    converter.body_width = 0
    return converter.handle(html) or ""


__all__ = ["convert_html"]
