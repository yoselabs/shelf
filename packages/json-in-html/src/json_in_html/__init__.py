"""json-in-html — pull structured JSON back out of an HTML page.

**Stop caring about where a page hid its structured data.** Modern SPAs (Next.js,
Nuxt) and most product / article pages embed their real content as JSON — in a
``<script type="application/json">`` blob, an ``application/ld+json`` schema, HTML5
microdata, OpenGraph meta tags, or a ``window.<var> = {...}`` assignment. Generic
markdown extractors strip these, leaving only navigation chrome. This extractor
scans an HTML string and returns the parsed payloads, ranked by downstream value.

Domain-independent: it detects and parses; it never fetches, and the *policy* for
what to do with each payload (which one to render, how to synthesize it) lives above
this primitive. The boundary type :class:`JsonPayload` is package-owned.

Malformed JSON is never raised — a tag that fails to parse is silently skipped, and
other tags on the same page still emit.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from selectolax.parser import HTMLParser

JsonSource = Literal[
    "next_data",
    "nuxt_data",
    "ld_json",
    "generic",
    "window_var",
    "microdata",
    "opengraph",
]
"""Closed set of detector identities a :class:`JsonPayload` can carry."""


@dataclass(slots=True, frozen=True)
class JsonPayload:
    """A parsed JSON-in-HTML payload.

    Attributes:
        source: The detector that matched — a stable contract for downstream
            prioritization (see :func:`rank_payloads`).
        data: The parsed JSON, a dict or a list. LD-JSON ``@graph`` can be a list
            at the root, so both container shapes are valid.
        script_id: The matched tag's ``id`` attribute when present, else ``None``.
            For the ``window_var`` source it repurposes to carry the variable name.
        byte_size: The length of the source JSON text.
    """

    source: JsonSource
    data: dict[str, Any] | list[Any]
    script_id: str | None
    byte_size: int


# --------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------- #


_PREFERRED_LD_TYPES: frozenset[str] = frozenset(
    {
        # commerce / editorial
        "Product",
        "Article",
        "NewsArticle",
        "ItemList",
        "BreadcrumbList",
        # entity / answer schemas (thin-but-complete pages: contact, org, event)
        "LocalBusiness",
        "Organization",
        "ContactPoint",
        "Event",
        "Recipe",
    }
)
_MIN_LD_FIELDS: int = 3


def extract_json_payloads(html: str) -> list[JsonPayload]:
    """Scan ``html`` for known JSON-in-HTML shapes and return parsed payloads.

    Order of detection (not priority — that is :func:`rank_payloads`'s job):

    1. ``<script id="__NEXT_DATA__" type="application/json">``
    2. ``<script id="__NUXT_DATA__">``
    3. ``<script type="application/ld+json">`` (may appear multiple times)
    4. ``<script type="application/json"[data-*]>`` — generic app-state
    5. HTML5 microdata + OpenGraph meta tags
    6. ``window.<name> = {...}`` JS-variable assignments

    Malformed JSON is silently skipped.

    Args:
        html: The raw HTML document text.

    Returns:
        The parsed payloads in detection order (empty on empty / unparsable input).
    """
    if not html:
        return []
    try:
        tree = HTMLParser(html)
    except Exception:  # noqa: BLE001 -- a broken parse is a no-payloads outcome, never a raise.
        return []

    out: list[JsonPayload] = []
    # 1. __NEXT_DATA__  2. __NUXT_DATA__  3. ld+json  4. generic app-state
    out.extend(_extract_framework_script(tree, "script#__NEXT_DATA__", "next_data", "__NEXT_DATA__"))
    out.extend(_extract_framework_script(tree, "script#__NUXT_DATA__", "nuxt_data", "__NUXT_DATA__"))
    out.extend(_extract_ld_json(tree))
    out.extend(_extract_generic_json(tree))
    # 5. Microdata + OpenGraph — selectolax-native attribute walk.
    out.extend(_extract_microdata_and_og(tree))
    # 6. window.<name> = {...} JS-variable assignments.
    out.extend(_extract_window_vars(tree))
    return out


def _extract_framework_script(tree: HTMLParser, selector: str, source: JsonSource, script_id: str) -> list[JsonPayload]:
    """Extract a single-id framework app-state script (``__NEXT_DATA__`` / ``__NUXT_DATA__``).

    Args:
        tree: The parsed HTML tree.
        selector: The selectolax CSS selector for the id-bearing script tag.
        source: The :class:`JsonSource` to stamp on the payload.
        script_id: The fixed script id carried on the payload.

    Returns:
        Zero or more payloads, one per matched, parseable tag.
    """
    out: list[JsonPayload] = []
    for node in tree.css(selector):
        body = node.text(strip=False) or ""
        payload = _try_parse(body)
        if payload is not None:
            out.append(JsonPayload(source=source, data=payload, script_id=script_id, byte_size=len(body)))
    return out


def _extract_ld_json(tree: HTMLParser) -> list[JsonPayload]:
    """Extract every ``<script type="application/ld+json">`` (often multiple per page).

    Args:
        tree: The parsed HTML tree.

    Returns:
        Zero or more ``ld_json`` payloads.
    """
    out: list[JsonPayload] = []
    for node in tree.css('script[type="application/ld+json"]'):
        body = node.text(strip=False) or ""
        payload = _try_parse(body)
        if payload is not None:
            out.append(JsonPayload(source="ld_json", data=payload, script_id=node.attributes.get("id"), byte_size=len(body)))
    return out


def _extract_generic_json(tree: HTMLParser) -> list[JsonPayload]:
    """Extract generic ``<script type="application/json">`` app-state (Yandex-style).

    Skips the id-bearing framework tags already captured upstream.

    Args:
        tree: The parsed HTML tree.

    Returns:
        Zero or more ``generic`` payloads.
    """
    out: list[JsonPayload] = []
    for node in tree.css('script[type="application/json"]'):
        if node.attributes.get("id") in ("__NEXT_DATA__", "__NUXT_DATA__"):
            continue
        body = node.text(strip=False) or ""
        payload = _try_parse(body)
        if payload is not None:
            out.append(JsonPayload(source="generic", data=payload, script_id=node.attributes.get("id"), byte_size=len(body)))
    return out


def _extract_window_vars(tree: HTMLParser) -> list[JsonPayload]:
    """Extract ``window.<name> = {...}`` app-state from ``text/javascript`` scripts.

    Targets initial-state patterns common to older / custom SPAs (Yandex's
    ``window.state``, classic Redux ``window.__INITIAL_STATE__``, generic
    ``window.__PRELOADED_STATE__`` / ``window.__APP_DATA__``).

    Args:
        tree: The parsed HTML tree.

    Returns:
        Zero or more ``window_var`` payloads.
    """
    out: list[JsonPayload] = []
    for node in tree.css("script"):
        script_type = (node.attributes.get("type") or "").lower()
        # Skip the application/json paths handled above and external scripts.
        if script_type and script_type not in ("text/javascript", "application/javascript", "module"):
            continue
        body = node.text(strip=False) or ""
        if not body or len(body) < 32:
            continue
        for var_name, expr in _scan_window_var_assignments(body):
            parsed = _try_parse(expr)
            if parsed is not None:
                out.append(JsonPayload(source="window_var", data=parsed, script_id=var_name, byte_size=len(expr)))
    return out


def rank_payloads(payloads: list[JsonPayload]) -> list[JsonPayload]:
    """Order payloads by descending downstream value.

    Bucket order (adds microdata + opengraph):

    0. ld_json strong (Product/Article/ItemList/BreadcrumbList/NewsArticle >=3 fields)
    1. microdata strong (same @type set, >=3 fields)
    2. next_data, nuxt_data (framework app state)
    3. opengraph (metadata, not body — always after framework state)
    4. ld_json weak, microdata weak
    5. window_var
    6. generic

    Within each bucket, larger payloads rank first (more data to synthesize).

    Args:
        payloads: The payloads to order.

    Returns:
        A new list sorted by ``(bucket, -byte_size)``.
    """

    def bucket(p: JsonPayload) -> int:
        if p.source == "ld_json":
            return 0 if _ld_json_strong(p.data) else 4
        if p.source == "microdata":
            return 1 if _microdata_strong(p.data) else 4
        if p.source in ("next_data", "nuxt_data"):
            return 2
        if p.source == "opengraph":
            return 3
        if p.source == "window_var":
            return 5
        return 6  # generic

    return sorted(payloads, key=lambda p: (bucket(p), -p.byte_size))


def _ld_json_strong(data: dict[str, Any] | list[Any]) -> bool:
    """Report whether an LD-JSON payload carries a strong (answer-bearing) schema.

    A payload is strong if it (or a top-level ``@graph`` entry) is one of the
    preferred types AND has >=3 populated fields beyond ``@type`` / ``@context``.
    Real-world LD-JSON often nests inside ``@graph``; this walks one level down.

    Args:
        data: The parsed LD-JSON value.

    Returns:
        True when a preferred, sufficiently-populated type is present.
    """
    candidates: list[dict[str, Any]] = []
    if isinstance(data, dict):
        graph = data.get("@graph")
        if isinstance(graph, list):
            candidates.extend(item for item in graph if isinstance(item, dict))
        candidates.append(data)
    elif isinstance(data, list):
        candidates.extend(item for item in data if isinstance(item, dict))

    for entry in candidates:
        entry_type = entry.get("@type")
        # @type can be a string or a list of strings.
        types: set[str] = set()
        if isinstance(entry_type, str):
            types.add(entry_type)
        elif isinstance(entry_type, list):
            types.update(t for t in entry_type if isinstance(t, str))
        if not types & _PREFERRED_LD_TYPES:
            continue
        populated = sum(1 for k, v in entry.items() if not k.startswith("@") and v not in (None, "", [], {}))
        if populated >= _MIN_LD_FIELDS:
            return True
    return False


# Names worth scanning. Conservative list — only patterns that, when present,
# carry initial app/page state. NOT generic `window.foo` (would over-match).
_WINDOW_VAR_NAMES: tuple[str, ...] = (
    "state",
    "__INITIAL_STATE__",
    "__PRELOADED_STATE__",
    "__APP_DATA__",
    "__APP_STATE__",
    "__DATA__",
    "__REDUX_STATE__",
    "__SSR__",
    "__APOLLO_STATE__",
    "__NUXT__",
)
_WINDOW_VAR_PREFIXES: tuple[re.Pattern[str], ...] = tuple(re.compile(rf"\bwindow\.{re.escape(name)}\s*=\s*") for name in _WINDOW_VAR_NAMES)


def _scan_window_var_assignments(js: str) -> list[tuple[str, str]]:
    """Find ``window.<NAME> = {...}`` assignments in a JS body.

    The expression text is the substring from the first ``{`` (or ``[``) after the
    ``=`` up through the matching balanced closer, scanned with string-aware bracket
    counting. Only NAMEs in ``_WINDOW_VAR_NAMES`` are scanned. No JS evaluation —
    only right-hand sides that parse as JSON survive ``_try_parse`` downstream.

    Args:
        js: The JavaScript source text.

    Returns:
        ``(var_name, json_expression_text)`` tuples, one per matched assignment.
    """
    out: list[tuple[str, str]] = []
    for name, prefix_re in zip(_WINDOW_VAR_NAMES, _WINDOW_VAR_PREFIXES, strict=True):
        for m in prefix_re.finditer(js):
            expr = _balanced_json_expr(js, m.end())
            if expr is not None:
                out.append((name, expr))
    return out


def _balanced_json_expr(js: str, start: int) -> str | None:
    """Return the balanced ``{...}`` / ``[...]`` expression beginning at ``start``.

    Scans with string-aware bracket counting so braces inside string literals do
    not confuse the depth counter.

    Args:
        js: The JavaScript source text.
        start: The index of the expected opening ``{`` or ``[``.

    Returns:
        The substring through the matching closer, or ``None`` when ``start`` is not
        an opener or the expression never balances.
    """
    if start >= len(js):
        return None
    opener = js[start]
    if opener not in "{[":
        return None
    closer = "}" if opener == "{" else "]"
    depth = 0
    in_string: str | None = None  # quote char when inside a string
    i = start
    n = len(js)
    while i < n:
        ch = js[i]
        if in_string is not None:
            if ch == "\\":
                i += 2
                continue
            if ch == in_string:
                in_string = None
        elif ch in ('"', "'"):
            in_string = ch
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return js[start : i + 1]
        i += 1
    return None


def _try_parse(body: str) -> dict[str, Any] | list[Any] | None:
    """Parse ``body`` as JSON, returning the container value or ``None``.

    Args:
        body: The candidate JSON text.

    Returns:
        The parsed dict or list on success; ``None`` on malformed JSON or a
        non-container scalar root.
    """
    if not body or not body.strip():
        return None
    try:
        parsed = json.loads(body)
    except (ValueError, json.JSONDecodeError):
        return None
    if isinstance(parsed, (dict, list)):
        return parsed
    return None


# --------------------------------------------------------------------- #
# Microdata, OpenGraph
# --------------------------------------------------------------------- #


def _extract_microdata_and_og(tree: HTMLParser) -> list[JsonPayload]:
    """Pull HTML5 microdata + OpenGraph meta tags off the selectolax tree.

    No extruct / rdflib dependency — the spec for both is a tractable attribute
    walk. RDFa is intentionally not covered: open-web hit rate is academic-only and
    the rdflib-shaped cost (transitive ~MB) is not justified today.

    Args:
        tree: The parsed HTML tree.

    Returns:
        Up to two payloads (``microdata`` and/or ``opengraph``), each present only
        when its detector matched something.
    """
    out: list[JsonPayload] = []

    items = _walk_microdata(tree)
    if items:
        try:
            byte_size = len(json.dumps(items))
        except (TypeError, ValueError):
            byte_size = 0
        out.append(JsonPayload(source="microdata", data=items, script_id=None, byte_size=byte_size))

    og = _collect_opengraph(tree)
    if og:
        try:
            byte_size = len(json.dumps(og))
        except (TypeError, ValueError):
            byte_size = 0
        out.append(JsonPayload(source="opengraph", data=og, script_id=None, byte_size=byte_size))

    return out


# Microdata HTML5 value-extraction table (per WHATWG spec section 5.2.6 "Values"):
# the source attribute varies by tag.
_MICRODATA_VALUE_ATTR: dict[str, str] = {
    "meta": "content",
    "audio": "src",
    "embed": "src",
    "iframe": "src",
    "img": "src",
    "source": "src",
    "track": "src",
    "video": "src",
    "a": "href",
    "area": "href",
    "link": "href",
    "object": "data",
    "data": "value",
    "meter": "value",
    "time": "datetime",
}


def _walk_microdata(tree: HTMLParser) -> list[dict[str, Any]]:
    """Walk every top-level ``[itemscope]`` node and collect its properties.

    Top-level = scope nodes whose nearest ``[itemscope]`` ancestor is themselves.
    Nested itemscope items recurse as dicts under the parent's properties.

    Args:
        tree: The parsed HTML tree.

    Returns:
        A list of ``{"type": [<itemtype>, ...], "properties": {...}}`` records.
    """
    scopes = tree.css("[itemscope]")
    if not scopes:
        return []
    out: list[dict[str, Any]] = []
    for node in scopes:
        # Skip if a parent is also itemscope (we only want top-level entries).
        parent = node.parent
        nested = False
        while parent is not None:
            attrs = parent.attributes
            if attrs is not None and "itemscope" in attrs:
                nested = True
                break
            parent = parent.parent
        if nested:
            continue
        out.append(_extract_microdata_item(node))
    return out


def _extract_microdata_item(scope_node: Any) -> dict[str, Any]:
    """Collect a single microdata item's type and properties.

    Args:
        scope_node: The ``[itemscope]`` node to extract.

    Returns:
        A ``{"type": [...], "properties": {...}}`` record; nested scopes recurse.
    """
    itemtype = (scope_node.attributes.get("itemtype") or "").strip()
    types = [t for t in itemtype.split() if t]
    properties: dict[str, Any] = {}

    # Collect [itemprop] descendants that do not belong to a deeper itemscope.
    for prop in scope_node.css("[itemprop]"):
        if prop == scope_node:
            continue
        # Walk up to confirm `prop` is owned by `scope_node` (not a nested scope).
        parent = prop.parent
        owner: Any = None
        while parent is not None:
            attrs = parent.attributes
            if attrs is not None and "itemscope" in attrs:
                owner = parent
                break
            parent = parent.parent
        if owner != scope_node:
            continue

        names = (prop.attributes.get("itemprop") or "").split()
        if not names:
            continue

        prop_attrs = prop.attributes
        if prop_attrs is not None and "itemscope" in prop_attrs:
            value: Any = _extract_microdata_item(prop)
        else:
            value = _microdata_value_of(prop)

        for name in names:
            existing = properties.get(name)
            if existing is None:
                properties[name] = value
            elif isinstance(existing, list):
                existing.append(value)
            else:
                properties[name] = [existing, value]

    return {"type": types, "properties": properties}


def _microdata_value_of(node: Any) -> str:
    """Return a microdata property node's value per the WHATWG value table.

    Args:
        node: The ``[itemprop]`` node (without its own ``itemscope``).

    Returns:
        The tag-appropriate attribute value, else the node's stripped text.
    """
    tag = (node.tag or "").lower()
    attr = _MICRODATA_VALUE_ATTR.get(tag)
    if attr:
        value = node.attributes.get(attr)
        if value is not None:
            return value
    return (node.text(strip=True) or "").strip()


_OG_PROPERTY_PREFIXES: tuple[str, ...] = ("og:", "article:", "product:", "book:", "profile:")


def _collect_opengraph(tree: HTMLParser) -> dict[str, str]:
    """Collect every ``<meta property="<og|article|product|book|profile>:*">``.

    Args:
        tree: The parsed HTML tree.

    Returns:
        A flat ``{property: content}`` dict (last-write-wins on duplicates); empty
        when nothing matches.
    """
    out: dict[str, str] = {}
    for node in tree.css("meta[property]"):
        prop = (node.attributes.get("property") or "").strip()
        if not prop.startswith(_OG_PROPERTY_PREFIXES):
            continue
        content = (node.attributes.get("content") or "").strip()
        if not content:
            continue
        out[prop] = content
    return out


def _microdata_strong(data: dict[str, Any] | list[Any]) -> bool:
    """Report whether microdata output carries a strong (answer-bearing) type.

    Microdata items come through as ``{"type": ["https://schema.org/Product"],
    "properties": {...}}``. Strong = recognized ``@type`` set + >=3 populated
    non-``@``-prefixed properties.

    Args:
        data: The microdata payload value (a list of items or a single item dict).

    Returns:
        True when a preferred, sufficiently-populated type is present.
    """
    items: list[dict[str, Any]] = []
    if isinstance(data, list):
        items = [it for it in data if isinstance(it, dict)]
    elif isinstance(data, dict):
        items = [data]

    for entry in items:
        raw_types = entry.get("type") or entry.get("@type")
        types: set[str] = set()
        if isinstance(raw_types, str):
            types.add(raw_types.rsplit("/", 1)[-1])
        elif isinstance(raw_types, list):
            for t in raw_types:
                if isinstance(t, str):
                    types.add(t.rsplit("/", 1)[-1])
        if not types & _PREFERRED_LD_TYPES:
            continue
        raw_props = entry.get("properties")
        props: dict[str, Any] = raw_props if isinstance(raw_props, dict) else entry
        populated = sum(1 for k, v in props.items() if not k.startswith("@") and v not in (None, "", [], {}))
        if populated >= _MIN_LD_FIELDS:
            return True
    return False


# --------------------------------------------------------------------- #
# Whole-response JSON (not JSON-in-script)
# --------------------------------------------------------------------- #


def is_json_content_type(content_type: str | None) -> bool:
    """Report whether a content-type is JSON-family.

    Matches ``application/json``, ``text/json``, and any ``application/<x>+json``
    suffix type (e.g. ``application/vnd.api+json``, ``application/ld+json``).
    Case-insensitive; tolerant of a trailing ``; charset=`` parameter.

    Args:
        content_type: A raw ``Content-Type`` header value, or ``None``.

    Returns:
        True for a JSON-family content-type.
    """
    if not content_type:
        return False
    ct = content_type.split(";", 1)[0].strip().lower()
    if ct in ("application/json", "text/json"):
        return True
    return ct.startswith("application/") and ct.endswith("+json")


def sniff_json_body(body: bytes) -> bool:
    """Report whether a raw response body parses as a JSON document.

    Recovers a JSON payload served under a non-JSON content-type (a misconfigured
    API returning JSON as ``text/html`` / ``text/plain``). Guarded by a ``{`` / ``[``
    prefix check on a bounded window so binary bodies (PDF, images) are never
    decoded or parsed.

    Args:
        body: The raw response body bytes.

    Returns:
        True when the body decodes to a JSON object or array.
    """
    if not body:
        return False
    # Cheap prefix guard on a bounded window — never lstrip a full (possibly
    # multi-MB) body. Real HTML opens with `<`; only a JSON prefix is decoded.
    if body[:64].lstrip()[:1] not in (b"{", b"["):
        return False
    return parse_json_response(body.decode("utf-8", errors="replace")) is not None


def parse_json_response(text: str) -> JsonPayload | None:
    """Parse a whole response body as a single top-level JSON document.

    Args:
        text: The full response body text.

    Returns:
        A ``JsonPayload(source="generic")`` on success, or ``None`` on any parse
        failure or a non-object/array root. Never raises.
    """
    stripped = text.strip()
    if not stripped:
        return None
    try:
        data = json.loads(stripped)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, (dict, list)):
        return None
    return JsonPayload(source="generic", data=data, script_id=None, byte_size=len(text))


def is_answer_bearing(payload: JsonPayload) -> bool:
    """Report whether a payload is a strong (answer-bearing) structured source.

    Strong = a preferred ``@type`` (``_PREFERRED_LD_TYPES``) with >=3 populated
    fields, for the ``ld_json`` and ``microdata`` sources only. Every other source
    (framework app-state, opengraph, window vars, generic) and every weak
    ld_json / microdata payload is page chrome, not an answer.

    Args:
        payload: The payload to classify.

    Returns:
        True when the payload carries an answer rather than page chrome.
    """
    if payload.source == "ld_json":
        return _ld_json_strong(payload.data)
    if payload.source == "microdata":
        return _microdata_strong(payload.data)
    return False


__all__ = [
    "JsonPayload",
    "JsonSource",
    "extract_json_payloads",
    "is_answer_bearing",
    "is_json_content_type",
    "parse_json_response",
    "rank_payloads",
    "sniff_json_body",
]
