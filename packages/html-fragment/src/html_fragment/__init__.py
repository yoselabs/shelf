r"""html-fragment — convert a server-supplied HTML fragment to markdown / plain text.

Many sites hand back their real content as a small HTML fragment rather than a full
document: a Discourse ``cooked``, a Habr ``textHtml``, a V2EX ``content_rendered``, an
HN Algolia comment ``text``. This primitive turns that fragment into link-preserving
markdown or collapsed plain text. lxml-backed, entity-decoded, permissive.

Boundary contract:

- :func:`to_markdown` — paragraphs / line breaks / list items / emphasis / ``<a href>``
  preserved as markdown; other tags stripped; entities decoded; ``\\xa0`` folded to
  space; when ``base_url`` is given, relative hrefs are resolved absolute.
- :func:`to_text` — tags stripped, entities decoded, ``\\xa0`` folded to space,
  whitespace collapsed. Use for inline titles / bylines.
- Empty / whitespace-only input returns ``""``.
- Malformed HTML never raises — lxml's permissive fragment parser tolerates it.

Domain-independent: it converts a fragment; it never fetches. No host-app imports.
"""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin

import lxml.html

__all__ = ["to_markdown", "to_text"]

_NBSP_RE = re.compile("[\xa0\u202f]")
_WS_COLLAPSE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_TRAILING_WS_RE = re.compile(r"[ \t]+\n")

# Tags that act as block-level paragraph separators.
_BLOCK_TAGS = frozenset({"p", "div", "section", "article", "header", "footer", "aside", "blockquote", "pre"})
# Heading tags — block-level; we keep their text and surround with blank lines.
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
# Inline emphasis tags → their markdown wrapper marker.
_INLINE_WRAP = {"em": "*", "i": "*", "strong": "**", "b": "**"}


def to_text(html: str) -> str:
    """Strip tags, decode entities, fold nbsp, and collapse internal whitespace.

    Args:
        html: An HTML fragment (possibly malformed).

    Returns:
        The plain-text content, entity-decoded with runs of spaces/tabs collapsed.
        Empty or whitespace-only input returns ``""``.
    """
    if not html or not html.strip():
        return ""
    # lxml's fragment parser tolerates malformed input.
    root = lxml.html.fragment_fromstring(html, create_parent="div")
    text = root.text_content()
    text = unescape(text)
    text = _NBSP_RE.sub(" ", text)
    text = _WS_COLLAPSE_RE.sub(" ", text)
    return text.strip()


def to_markdown(html: str, *, base_url: str | None = None) -> str:
    """Convert an HTML fragment to markdown.

    Preserves: paragraphs (blank-line-separated), ``<br>`` (single newline),
    ``<li>`` (leading ``- ``), ``<em>``/``<i>`` to ``*…*``, ``<strong>``/``<b>`` to
    ``**…**``, ``<a href>`` to ``[text](href)`` (absolutized against ``base_url`` when
    given). Drops all other tags; decodes entities; folds nbsp.

    Args:
        html: An HTML fragment (possibly malformed).
        base_url: When provided, relative ``href`` values are resolved absolute
            against it; when ``None``, hrefs are kept verbatim.

    Returns:
        The markdown rendering. Empty or whitespace-only input returns ``""``.
    """
    if not html or not html.strip():
        return ""
    root = lxml.html.fragment_fromstring(html, create_parent="div")
    out: list[str] = []
    _render(root, out, base_url=base_url, inside_block=False)
    text = "".join(out)
    text = unescape(text)
    text = _NBSP_RE.sub(" ", text)
    text = _TRAILING_WS_RE.sub("\n", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def _render(el: lxml.html.HtmlElement, out: list[str], *, base_url: str | None, inside_block: bool) -> None:
    """Render one element into ``out``, then append its tail text.

    Dispatches on the tag: inline emphasis wraps in ``*``/``**``, ``<br>`` and
    ``<li>`` get literal markers, ``<a>`` becomes a markdown link, and everything
    else flows through :func:`_render_flow` (block surrounds or transparent passthrough).
    """
    tag = (el.tag or "").lower() if isinstance(el.tag, str) else ""

    marker = _INLINE_WRAP.get(tag)
    if marker is not None:
        out.append(marker)
        _render_text_and_children(el, out, base_url=base_url, inside_block=inside_block)
        out.append(marker)
    elif tag == "br":
        out.append("\n")
    elif tag == "li":
        out.append("\n- ")
        _render_text_and_children(el, out, base_url=base_url, inside_block=True)
        out.append("\n")
    elif tag == "a":
        _render_anchor(el, out, base_url=base_url)
    else:
        _render_flow(el, out, base_url=base_url, inside_block=inside_block, tag=tag)

    if el.tail:
        out.append(el.tail)


def _render_anchor(el: lxml.html.HtmlElement, out: list[str], *, base_url: str | None) -> None:
    """Render an ``<a>`` as ``[label](href)`` (or bare label when it has no href)."""
    href = el.get("href") or ""
    if base_url and href:
        href = urljoin(base_url, href)
    # Collect inner text/markup for the link label.
    inner: list[str] = []
    _render_text_and_children(el, inner, base_url=base_url, inside_block=True)
    label = "".join(inner).strip()
    out.append(f"[{label}]({href})" if href else label)


def _render_flow(el: lxml.html.HtmlElement, out: list[str], *, base_url: str | None, inside_block: bool, tag: str) -> None:
    """Render a block or transparent element, surrounding block-level tags with blank lines."""
    # Block tags (including the synthetic root <div>) and headings get blank-line surrounds.
    is_block = tag in _BLOCK_TAGS or tag in _HEADING_TAGS
    if is_block and inside_block is False and out and "".join(out) and not "".join(out).endswith("\n\n"):
        # Only insert separators when not at the very start.
        out.append("\n\n")

    _render_text_and_children(el, out, base_url=base_url, inside_block=inside_block or is_block)

    if is_block:
        out.append("\n\n")


def _render_text_and_children(el: lxml.html.HtmlElement, out: list[str], *, base_url: str | None, inside_block: bool) -> None:
    """Emit the element's own text, then recurse into its children."""
    if el.text:
        out.append(el.text)
    _render_children(el, out, base_url=base_url, inside_block=inside_block)


def _render_children(el: lxml.html.HtmlElement, out: list[str], *, base_url: str | None, inside_block: bool) -> None:
    """Recurse into each child element in document order."""
    for child in el:
        _render(child, out, base_url=base_url, inside_block=inside_block)
