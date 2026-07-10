"""In-memory HTML → Markdown — the string-door companion to ``convert(path)``.

HTML is not one thing: the right tool depends on the *source kind*, not the MIME
type (docx-engine-verification, design.md D7). Two kinds, two intents:

- ``"web_page"`` (default) — HTML captured from a web page, carrying navigation,
  headers, footers, and other boilerplate. The intent is **extraction**: recover
  the main content and drop the chrome. Runs trafilatura first (best boilerplate
  removal) with an html2text fallback.
- ``"clean"`` — HTML already free of boilerplate (e.g. rendered from docx by
  mammoth). The intent is **faithful rendering**: every element is real content,
  lose nothing. Runs html2text directly — trafilatura's content-detection would
  *destroy* clean HTML (it strips headings and explodes tables when there is no
  page structure to anchor on; verified in the docx bench).

Passing the wrong kind is the one real failure mode: a web page rendered as
``"clean"`` keeps its nav/footer junk; a clean fragment extracted as
``"web_page"`` loses its structure. The caller knows its source, so it declares
it. :func:`convert_html` follows ``convert()``'s never-raises contract: a
``failed``-fidelity empty result when the chain gives up.

The consumer keeps its own presentation policy (how a low-fidelity result
surfaces); this is the conversion mechanism only.
"""

from __future__ import annotations

from typing import Literal

from convert_md.base import ConversionResult
from convert_md.engines import _result, _ver

SourceKind = Literal["web_page", "clean"]


def convert_html(
    html: str,
    *,
    url: str | None = None,
    source_kind: SourceKind = "web_page",
    include_links: bool = False,
) -> ConversionResult:
    """Convert an in-memory HTML string to Markdown, by source kind.

    Args:
        html: The raw HTML document text.
        url: The page's source URL, passed to trafilatura so relative links
            resolve against it. Only meaningful for ``source_kind="web_page"``.
        source_kind: ``"web_page"`` (default) extracts main content from a
            boilerplate-bearing page (trafilatura → html2text). ``"clean"``
            faithfully renders already-clean HTML (html2text only), skipping the
            web extractor which would damage it.
        include_links: when ``True`` and the trafilatura path runs, in-body
            anchors survive as ``[label](url)`` Markdown instead of being
            flattened to their text. Off by default (link-free prose is the
            common case); a consumer that reasons over the anchor graph opts in.
            Only affects ``source_kind="web_page"`` (the html2text path always
            preserves links).

    Returns:
        A graded :class:`ConversionResult`. Never raises: if the chain extracts
        nothing, a ``failed``-fidelity empty result is returned so the caller can
        still proceed.
    """
    source_size = len(html.encode("utf-8", errors="replace"))

    if source_kind == "web_page":
        markdown = _extract_trafilatura(html, url=url, include_links=include_links)
        if markdown.strip():
            return _result(markdown, f"trafilatura@{_ver('trafilatura')}", source_size)

    markdown = _extract_html2text(html)
    if markdown.strip():
        return _result(markdown, f"html2text@{_ver('html2text')}", source_size)

    return ConversionResult(
        body_markdown="",
        engine=f"html2text@{_ver('html2text')}",
        fidelity="failed",
        lost=["all"],
        warnings=["conversion_failed"],
    )


def _extract_trafilatura(html: str, *, url: str | None, include_links: bool = False) -> str:
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
            include_links=include_links,
        )
        or ""
    )


def _extract_html2text(html: str) -> str:
    """Faithful HTML → Markdown via html2text, unbounded line width."""
    try:
        import html2text  # noqa: PLC0415 — lazy import keeps package import cheap
    except ImportError:  # pragma: no cover
        return ""
    converter = html2text.HTML2Text()
    converter.body_width = 0
    return converter.handle(html) or ""


__all__ = ["SourceKind", "convert_html"]
