"""HTML → Markdown extraction + metadata parsing — reusable microsofware.

The body Markdown is composed from :func:`convert_md.convert_html` (trafilatura-first,
url-aware, never-raises); this package layers on top of it structured metadata
(title / byline / date via ``trafilatura.extract_metadata``), a heading outline, and
role-classified links (both via ``selectolax``). Zero consumer-domain imports.

Boundary types (:class:`ExtractedHeading`, :class:`ExtractedLink`,
:class:`ExtractedContent`) are package-owned frozen dataclasses. A consumer maps
them to whatever its own response envelope uses.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import partial
from typing import Any

import trafilatura
from convert_md import convert_html
from selectolax.parser import HTMLParser

# --------------------------------------------------------------------- #
# Boundary types
# --------------------------------------------------------------------- #


@dataclass(slots=True, frozen=True)
class ExtractedHeading:
    """One heading in the page outline: its level (1..6) and text."""

    level: int  # 1..6
    text: str


@dataclass(slots=True, frozen=True)
class ExtractedLink:
    """One extracted anchor: its text, href, and DOM-derived role.

    ``role`` ∈ ``{"primary", "nav", "meta", "footer"}``:

    - ``"primary"`` — parent ∈ ``<article>`` / ``<main>`` / ``.content`` (the body)
    - ``"nav"`` — parent ∈ ``<nav>`` or ``role="navigation"``
    - ``"footer"`` — parent ∈ ``<footer>``
    - ``"meta"`` — parent ∈ ``<header>`` / ``<aside>``

    The defensive default is ``"primary"`` — unclassified links keep flowing to
    callers; filtering is a caller-side concern.
    """

    anchor: str
    href: str
    role: str = "primary"


@dataclass(slots=True, frozen=True)
class ExtractedContent:
    """The full extraction result: body Markdown plus structured metadata."""

    content_md: str
    title: str | None = None
    byline: str | None = None
    published: date | None = None
    headings: list[ExtractedHeading] = field(default_factory=list)
    links: list[ExtractedLink] = field(default_factory=list)
    score: float | None = None


# --------------------------------------------------------------------- #
# Extraction (sync, async-chokepointed)
# --------------------------------------------------------------------- #


# Tags / role attributes that flag each link role. Walked toward the
# DOM root from the anchor; first match wins.
_ROLE_TAG_MAP: dict[str, str] = {
    "nav": "nav",
    "footer": "footer",
    "header": "meta",
    "aside": "meta",
    "article": "primary",
    "main": "primary",
}


def _classify_link_role(node: Any) -> str:
    """Walk ancestors; return the first matching role, else ``"primary"``.

    Cheap O(depth) traversal — a typical anchor sits 3-8 levels deep. Falls back to
    ``"primary"`` so unclassified links keep flowing to callers.

    Args:
        node: The selectolax anchor node to classify.

    Returns:
        The classified role string.
    """
    parent = node.parent
    while parent is not None:
        tag = (parent.tag or "").lower()
        if tag in _ROLE_TAG_MAP:
            return _ROLE_TAG_MAP[tag]
        attrs = parent.attributes
        if attrs:
            role = (attrs.get("role") or "").lower()
            if role == "navigation":
                return "nav"
            if role == "contentinfo":
                return "footer"
            if role == "banner":
                return "meta"
            if role in {"main", "article"}:
                return "primary"
        parent = parent.parent
    return "primary"


def _contact_label(href: str) -> str | None:
    """Derive a label for a label-less contact anchor, or ``None`` if not one.

    ``mailto:support@x.com`` → ``support@x.com``; ``tel:+900000`` → ``+900000``.
    Any other scheme returns ``None`` (the anchor stays dropped).
    """
    lowered = href.lower()
    for scheme in ("mailto:", "tel:"):
        if lowered.startswith(scheme):
            value = href[len(scheme):].split("?", 1)[0].strip()
            return value or None
    return None


def _parse_date(value: str | None) -> date | None:
    """Parse trafilatura's date field (``YYYY-MM-DD`` or ISO timestamp) → ``date``.

    Args:
        value: The raw date string, or ``None``.

    Returns:
        The parsed date, or ``None`` when absent or invalid.
    """
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()  # noqa: DTZ007 — date-only, no tz
    except ValueError:
        return None


def _extract_sync(html: str, url: str, *, include_links: bool = False) -> ExtractedContent:
    """Blocking extraction — never call from async paths directly.

    Args:
        html: The raw HTML document text.
        url: The page's source URL (for relative-link resolution).
        include_links: pass through to :func:`convert_md.convert_html` so
            in-body anchors survive as ``[label](url)`` in ``content_md``.

    Returns:
        The assembled :class:`ExtractedContent`.
    """
    result = convert_html(html, url=url, include_links=include_links)
    content_md = result.body_markdown

    title: str | None = None
    byline: str | None = None
    published: date | None = None
    metadata = trafilatura.extract_metadata(html)
    if metadata is not None:
        title = metadata.title or None
        byline = metadata.author or None
        published = _parse_date(getattr(metadata, "date", None))

    headings: list[ExtractedHeading] = []
    links: list[ExtractedLink] = []
    try:
        tree = HTMLParser(html)
        for node in tree.css("h1, h2, h3, h4, h5, h6"):
            level = int(node.tag[1])
            text = (node.text() or "").strip()
            if text:
                headings.append(ExtractedHeading(level=level, text=text))
        for a in tree.css("a[href]"):
            href = a.attributes.get("href") or ""
            anchor = (a.text() or "").strip()
            if not href:
                continue
            if not anchor:
                # A label-less anchor is normally chrome (an icon link) and is
                # dropped. The exception is a contact link (``mailto:`` /
                # ``tel:``) whose href IS the datum the caller wants — keep it,
                # deriving a label from the scheme's value so it is not empty.
                derived = _contact_label(href)
                if derived is None:
                    continue
                anchor = derived
            role = _classify_link_role(a)
            links.append(ExtractedLink(anchor=anchor, href=href, role=role))
    except Exception:  # noqa: BLE001, S110 — selectolax parse errors are non-fatal; content_md is the primary output
        pass

    return ExtractedContent(
        content_md=content_md,
        title=title,
        byline=byline,
        published=published,
        headings=headings,
        links=links,
        score=None,
    )


async def extract_markdown(html: str, url: str, *, include_links: bool = False) -> ExtractedContent:
    """Extract page content + metadata, off-thread.

    The only public async entry point. Punts the blocking extraction to a worker
    thread so async callers never stall on trafilatura / selectolax.

    Args:
        html: The raw HTML document text.
        url: The page's source URL (for relative-link resolution).
        include_links: keep in-body anchors as ``[label](url)`` in ``content_md``
            (passed through to :func:`convert_md.convert_html`). Off by default.

    Returns:
        The assembled :class:`ExtractedContent`.
    """
    return await asyncio.to_thread(partial(_extract_sync, html, url, include_links=include_links))


# --------------------------------------------------------------------- #
# Metadata — OG, Twitter, JSON-LD
# --------------------------------------------------------------------- #


def _flatten_jsonld(obj: Any, prefix: str, out: dict[str, str]) -> None:
    """Best-effort flatten of one JSON-LD object into dot-keyed strings.

    Only top-level scalar fields end up in ``out``. Nested objects/arrays are
    skipped — agents and renderers rarely need deep traversal.

    Args:
        obj: The candidate JSON-LD object (ignored unless a dict).
        prefix: The dotted key prefix for emitted fields.
        out: The accumulator dict, mutated in place.
    """
    if not isinstance(obj, dict):
        return
    for key, value in obj.items():
        if isinstance(value, str | int | float | bool):
            out[f"{prefix}.{key}"] = str(value)


def parse_metadata(html: str) -> dict[str, str]:
    """Return a flat dot-keyed dict of OG, Twitter, and JSON-LD metadata.

    Missing fields are simply omitted (no ``None`` values). Only the first JSON-LD
    block is parsed (``jsonld[0].*``). Pure function.

    Args:
        html: The raw HTML document text.

    Returns:
        A flat mapping of dotted metadata keys to string values.
    """
    out: dict[str, str] = {}
    tree = HTMLParser(html)

    for meta in tree.css("meta[property^='og:']"):
        prop = meta.attributes.get("property") or ""
        content = meta.attributes.get("content") or ""
        if prop and content:
            key = prop.replace(":", ".", 1)
            out[key] = content

    for meta in tree.css("meta[name^='twitter:']"):
        name = meta.attributes.get("name") or ""
        content = meta.attributes.get("content") or ""
        if name and content:
            key = name.replace(":", ".", 1)
            out[key] = content

    jsonld_nodes = tree.css("script[type='application/ld+json']")
    if jsonld_nodes:
        raw = (jsonld_nodes[0].text() or "").strip()
        if raw:
            try:
                obj = json.loads(raw)
                first = obj[0] if isinstance(obj, list) and obj else obj
                _flatten_jsonld(first, "jsonld[0]", out)
            except (ValueError, IndexError):
                pass

    return out


__all__ = (
    "ExtractedContent",
    "ExtractedHeading",
    "ExtractedLink",
    "extract_markdown",
    "parse_metadata",
)
