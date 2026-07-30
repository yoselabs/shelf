"""record-mine detection — locate the dominant repeated record region.

Pure HTML -> records; package-owned, domain-independent.

Article extractors (trafilatura and friends) locate one main-content node and
discard repeated DOM structure as boilerplate. On a listing / index / thread
page there is no single article — the page *is* N repeated records — so such an
extractor guts it. This module recovers the records.

Detection is **tree-aware**: each `(tag, first-class-token)` signature is
counted document-wide, not only among the direct children of one container,
so a recursively nested record region (a threaded comment tree) is located as
well as a flat sibling list. The occurrences of the chosen signature are the
records, rooted at their lowest common ancestor; each is rendered at its
nesting depth using its **own scope** (text/links excluding nested
same-signature child-records).

A signature must clear three guards to be a candidate — non-empty class
token, parent-signature consistency, heading presence — and an ancestor
tie-break resolves a near-tie in favour of the outer wrapper.

One shape is invisible to those guards and has its own path: a **definition
list**. `<dt>`/`<dd>` are classless and heading-less in every real listing, so
guards (a) and (c) reject them — yet a `<dl>` is an association list by
specification, which is the very thing those guards try to infer from class
soup. `_definition_list_region` runs as a FALLBACK after signature detection
finds nothing, so no page that already yields a region changes what it yields.

The detector self-gates: when neither path finds a region, `extract_records`
returns `None` and the caller falls through (an article, a near-empty JS shell,
a reference doc — none is a record region).
"""

from __future__ import annotations

import contextlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import median
from typing import TYPE_CHECKING

import lxml.html

from .models import Record, RecordSet
from .render import render_record

if TYPE_CHECKING:
    from collections.abc import Iterator

# A record region needs at least this many repeated, content-bearing records.
_MIN_RECORDS = 5
# A content-bearing record carries more than this many chars of own-scope text.
_MIN_RECORD_TEXT = 20
# Per-record text is capped in the ranking score so a few huge records do not
# outweigh a genuine many-record listing.
_MEDIAN_TEXT_CAP = 400
# Hard cap on rendered / emitted records — parity with the JSON-synth row cap.
_MAX_RECORDS = 50
# Guard (b): the records must share one dominant parent signature.
_CONSISTENCY_MIN = 0.70
# Guard (c): at least this fraction of records must carry a heading.
_HEADING_FRAC_MIN = 0.50
# Candidates scoring within this band of the best are "tied" — the ancestor
# tie-break then prefers the outer wrapper.
_TIE_BAND = 0.85
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

# A `(tag, first-class-token)` structural signature.
_Signature = tuple[str, str]


@dataclass(slots=True)
class _Candidate:
    """A scratch candidate signature evaluated during detection."""

    sig: _Signature
    content: list[lxml.html.HtmlElement]
    score: float
    consistency: float
    heading_frac: float


def _signature(el: lxml.html.HtmlElement) -> _Signature:
    if not isinstance(el.tag, str):
        return ("", "")
    classes = (el.get("class") or "").split()
    return (el.tag, classes[0] if classes else "")


def _el_label(el: lxml.html.HtmlElement) -> str:
    tag, cls = _signature(el)
    return f"{tag or '?'}.{cls or '-'}"


def _collapse(text: str) -> str:
    return " ".join(text.split())


# Strikethrough tags — their text is a superseded value (e.g. an original/list
# price crossed out). Marked as markdown `~~…~~` so the projection preserves the
# list-vs-sale distinction for the consumer instead of flattening it away.
_STRIKE_TAGS = frozenset({"del", "s", "strike"})


def _apply_markup(el: lxml.html.HtmlElement, text: str) -> str:
    """Wrap answer-bearing markup so it survives the text projection."""
    if isinstance(el.tag, str) and el.tag in _STRIKE_TAGS and text.strip():
        return f"~~{text}~~"
    return text


def _own_text(el: lxml.html.HtmlElement, record_sig: _Signature) -> str:
    """Concatenate the text of `el`'s own scope.

    Descends into children but prunes any nested same-signature child-record
    subtree (its text belongs to that child's own scope, not the parent's).

    A separator is inserted at **element boundaries** when two adjacent
    contributions would otherwise fuse (neither side carries whitespace), so
    distinct inline values — a price and an abutting discount badge — stay
    distinguishable. Text-flow continuity is preserved: an element's tail text
    concatenates normally (`<b>foo</b>bar` stays `foobar`); only element
    contributions are guarded. This is the structural elimination of the
    value-blind no-separator projection; it is content-agnostic — no branch
    inspects whether a fragment looks like a price or percentage.

    Args:
        el: The record element whose own-scope text is collected.
        record_sig: The record signature whose nested occurrences are pruned.

    Returns:
        The concatenated own-scope text.
    """
    parts: list[str] = []
    if el.text:
        parts.append(el.text)
    for child in el:
        if isinstance(child.tag, str) and _signature(child) != record_sig:
            child_text = _apply_markup(child, _own_text(child, record_sig))
            if child_text:
                if parts and not parts[-1][-1:].isspace() and not child_text[:1].isspace():
                    parts.append(" ")
                parts.append(child_text)
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _own_elements(el: lxml.html.HtmlElement, record_sig: _Signature) -> Iterator[lxml.html.HtmlElement]:
    """Yield `el`'s own-scope descendants, skipping nested same-signature records.

    Args:
        el: The record element whose own-scope descendants are yielded.
        record_sig: The record signature whose nested subtrees are skipped.

    Yields:
        Each own-scope descendant element.
    """
    for child in el:
        if not isinstance(child.tag, str):
            continue
        if _signature(child) == record_sig:
            continue
        yield child
        yield from _own_elements(child, record_sig)


def _own_links(el: lxml.html.HtmlElement, record_sig: _Signature) -> tuple[tuple[str, str], ...]:
    out: list[tuple[str, str]] = []
    for d in _own_elements(el, record_sig):
        if d.tag == "a":
            href = d.get("href")
            if href:
                out.append((_collapse(d.text_content()), href))
    return tuple(out)


def _own_has_link(el: lxml.html.HtmlElement, record_sig: _Signature) -> bool:
    return any(d.tag == "a" and d.get("href") for d in _own_elements(el, record_sig))


def _own_has_heading(el: lxml.html.HtmlElement, record_sig: _Signature) -> bool:
    return any(d.tag in _HEADING_TAGS or d.get("role") == "heading" for d in _own_elements(el, record_sig))


def _heading(el: lxml.html.HtmlElement, record_sig: _Signature) -> tuple[str, tuple[str, str] | None] | None:
    """Find the record's heading — its own-scope text and first anchor.

    Args:
        el: The record element whose own-scope heading is sought.
        record_sig: The record signature whose nested subtrees are skipped.

    Returns:
        `(heading_text, link)` when an own-scope heading is found, where `link`
        is the first anchor's `(anchor_text, href)` inside it (or `None` if the
        heading has no link); `None` when no own-scope heading exists at all.
    """
    for d in _own_elements(el, record_sig):
        if d.tag in _HEADING_TAGS or d.get("role") == "heading":
            heading_text = _collapse(d.text_content())
            if not heading_text:
                continue
            for a in d.iter("a"):
                href = a.get("href")
                if href:
                    return heading_text, (_collapse(a.text_content()), href)
            return heading_text, None
    return None


def _depth(el: lxml.html.HtmlElement, record_sig: _Signature) -> int:
    """Count of `el`'s ancestors that share the record signature."""
    d = 0
    p = el.getparent()
    while p is not None:
        if _signature(p) == record_sig:
            d += 1
        p = p.getparent()
    return d


def _parent_signature(el: lxml.html.HtmlElement) -> _Signature:
    p = el.getparent()
    return _signature(p) if p is not None else ("", "")


def _lca(elements: list[lxml.html.HtmlElement]) -> lxml.html.HtmlElement | None:
    """Find the lowest common ancestor of `elements` — the record region root."""

    def ancestors(e: lxml.html.HtmlElement) -> list[lxml.html.HtmlElement]:
        chain: list[lxml.html.HtmlElement] = []
        cur: lxml.html.HtmlElement | None = e
        while cur is not None:
            chain.append(cur)
            cur = cur.getparent()
        return list(reversed(chain))

    common = ancestors(elements[0])
    for e in elements[1:]:
        aset = set(ancestors(e))
        common = [c for c in common if c in aset]
    return common[-1] if common else None


def _build_record(el: lxml.html.HtmlElement, record_sig: _Signature, depth: int) -> Record:
    text = _collapse(_own_text(el, record_sig))
    links = _own_links(el, record_sig)
    heading = _heading(el, record_sig)
    if heading is not None:
        heading_text, heading_link = heading
    else:
        # No own-scope heading. Keep the legacy heading-link fallback so a
        # consumer still gets a usable source link, but leave `heading_text`
        # unset so the renderer falls through to the text-led row.
        heading_text = None
        heading_link = max(links, key=lambda link: len(link[0])) if links else None
    return Record(
        text=text,
        links=links,
        heading_text=heading_text,
        heading_link=heading_link,
        depth=depth,
        markdown=render_record(
            text,
            links,
            depth,
            heading_text=heading_text,
            heading_link=heading_link,
        ),
    )


def _evaluate(sig: _Signature, members: list[lxml.html.HtmlElement]) -> _Candidate | None:
    """Score one signature group and compute its guard metrics.

    Args:
        sig: The `(tag, first-class-token)` signature being evaluated.
        members: The document-wide elements sharing that signature.

    Returns:
        A scored `_Candidate`, or `None` when the group cannot be a record region.
    """
    tag, cls = sig
    if not tag or not cls:  # guard (a): non-empty class token
        return None
    if len(members) < _MIN_RECORDS:
        return None
    content: list[lxml.html.HtmlElement] = []
    text_lens: list[int] = []
    for el in members:
        own = _collapse(_own_text(el, sig))
        if len(own) > _MIN_RECORD_TEXT and _own_has_link(el, sig):
            content.append(el)
            text_lens.append(len(own))
    if len(content) < _MIN_RECORDS:
        return None
    parent_sigs = Counter(_parent_signature(el) for el in content)
    consistency = parent_sigs.most_common(1)[0][1] / len(content)
    heading_frac = sum(_own_has_heading(el, sig) for el in content) / len(content)
    score = len(content) * min(median(text_lens), _MEDIAN_TEXT_CAP)
    return _Candidate(
        sig=sig,
        content=content,
        score=score,
        consistency=consistency,
        heading_frac=heading_frac,
    )


def _select(candidates: list[_Candidate]) -> _Candidate | None:
    """Apply guards (b) + (c), then pick the best with an ancestor tie-break.

    Args:
        candidates: The scored candidate signatures.

    Returns:
        The chosen candidate, or `None` when none clears the consistency and
        heading guards.
    """
    passed = [c for c in candidates if c.consistency >= _CONSISTENCY_MIN and c.heading_frac >= _HEADING_FRAC_MIN]
    if not passed:
        return None
    passed.sort(key=lambda c: c.score, reverse=True)
    best = passed[0].score
    tied = [c for c in passed if c.score >= _TIE_BAND * best]
    # Ancestor tie-break: prefer the candidate whose signature is the parent
    # signature of another tied candidate — the outer wrapper carries the
    # full record / the threading.
    for c in tied:
        if any(other is not c and c.sig == _parent_signature(other.content[0]) for other in tied):
            return c
    return tied[0]


def _parse_tree(html: str, base_url: str) -> lxml.html.HtmlElement | None:
    """Parse `html`, resolving relative hrefs against `base_url` when given."""
    try:
        tree = lxml.html.fromstring(html)
    except (ValueError, SyntaxError):
        return None
    if base_url:
        with contextlib.suppress(ValueError, SyntaxError):
            tree.make_links_absolute(base_url)
    return tree


def _group_signatures(tree: lxml.html.HtmlElement) -> dict[_Signature, list[lxml.html.HtmlElement]]:
    """Group every element under `tree` by its structural signature — one pass."""
    groups: dict[_Signature, list[lxml.html.HtmlElement]] = defaultdict(list)
    for el in tree.iter():
        if isinstance(el.tag, str):
            groups[_signature(el)].append(el)
    return groups


def _build_record_set(chosen: _Candidate) -> RecordSet:
    """Build the `RecordSet` from the chosen candidate's record occurrences."""
    sig = chosen.sig
    members = chosen.content[:_MAX_RECORDS]
    records: list[Record] = []
    max_depth = 0
    for el in members:
        depth = _depth(el, sig)
        max_depth = max(max_depth, depth)
        records.append(_build_record(el, sig, depth))

    container = _lca(members)
    return RecordSet(
        records=tuple(records),
        container=_el_label(container) if container is not None else "",
        child_signature=f"{sig[0]}.{sig[1] or '-'}",
        max_depth=max_depth,
    )


# A `<dd>`'s own-scope signature. Classless by construction in the shape this
# path exists for; used so a NESTED definition list's records are pruned from
# their parent's scope exactly as the signature path prunes its own.
_DD_SIG: _Signature = ("dd", "")


def _definition_pairs(dl: lxml.html.HtmlElement) -> list[tuple[lxml.html.HtmlElement, lxml.html.HtmlElement]]:
    """Pair each `<dd>` with its nearest preceding `<dt>` inside one `<dl>`.

    Per the HTML spec a `<dl>` is an association list: `<dt>` names a term,
    `<dd>` describes it. Multiple `<dd>`s may follow one `<dt>`; each is paired
    with that term, which is why the term is not consumed on first use.
    """
    pairs: list[tuple[lxml.html.HtmlElement, lxml.html.HtmlElement]] = []
    term: lxml.html.HtmlElement | None = None
    for child in dl:
        if not isinstance(child.tag, str):
            continue
        if child.tag == "dt":
            term = child
        elif child.tag == "dd" and term is not None:
            pairs.append((term, child))
    return pairs


def _definition_list_region(
    tree: lxml.html.HtmlElement,
) -> tuple[list[tuple[lxml.html.HtmlElement, lxml.html.HtmlElement]], lxml.html.HtmlElement] | None:
    """Locate the largest content-bearing `<dl>` record region, or `None`.

    Why this is not just another signature: BOTH signature guards are blind to
    this shape, and both for the same reason. `<dt>`/`<dd>` are classless in
    every real definition listing, so guard (a) rejects `("dd", "")`; and they
    carry no `h1`-`h6`, so guard (c) rejects them on heading presence. Those
    guards are PROXIES for "this element is a record" — inferred, because in
    `<div>`/`<li>` soup nothing states it. A `<dl>` states it outright, so the
    proxies are not merely unnecessary here, they are actively wrong.

    The content floors still apply, and are what keep a two-item glossary beside
    an article from hijacking the page: `_MIN_RECORDS` pairs, each with more than
    `_MIN_RECORD_TEXT` chars of own-scope description, and a link SOMEWHERE IN
    THE PAIR — the term commonly carries it (`<dt><a href=…>`), so requiring one
    in the description alone would reject the shape this exists for.
    """
    best: tuple[list[tuple[lxml.html.HtmlElement, lxml.html.HtmlElement]], lxml.html.HtmlElement] | None = None
    for dl in tree.iter("dl"):
        kept = [
            (term, desc)
            for term, desc in _definition_pairs(dl)
            if len(_collapse(_own_text(desc, _DD_SIG))) > _MIN_RECORD_TEXT and (_own_links(desc, _DD_SIG) or _own_links(term, _DD_SIG))
        ]
        if len(kept) >= _MIN_RECORDS and (best is None or len(kept) > len(best[0])):
            best = (kept, dl)
    return best


def _build_definition_record(
    term: lxml.html.HtmlElement,
    desc: lxml.html.HtmlElement,
    depth: int,
) -> Record:
    """Build one record from a `<dt>`/`<dd>` pair.

    The term IS the heading — that is what `<dt>` means — so it is used directly
    rather than searched for among `h1`-`h6`. Links from both halves reach the
    consumer, term-first, because the term's link is the record's own address
    (an `/abs/…` id) while the description's links are incidental.
    """
    text = _collapse(_own_text(desc, _DD_SIG))
    term_links = _own_links(term, _DD_SIG)
    links = (*term_links, *(link for link in _own_links(desc, _DD_SIG) if link not in term_links))
    heading_text = _collapse(_own_text(term, _DD_SIG)) or None
    heading_link = term_links[0] if term_links else (links[0] if links else None)
    return Record(
        text=text,
        links=links,
        heading_text=heading_text,
        heading_link=heading_link,
        depth=depth,
        markdown=render_record(
            text,
            links,
            depth,
            heading_text=heading_text,
            heading_link=heading_link,
        ),
    )


def _build_definition_record_set(
    pairs: list[tuple[lxml.html.HtmlElement, lxml.html.HtmlElement]],
    container: lxml.html.HtmlElement,
) -> RecordSet:
    """Build the `RecordSet` for a located definition-list region."""
    kept = pairs[:_MAX_RECORDS]
    records: list[Record] = []
    max_depth = 0
    for term, desc in kept:
        depth = _depth(desc, _DD_SIG)
        max_depth = max(max_depth, depth)
        records.append(_build_definition_record(term, desc, depth))
    return RecordSet(
        records=tuple(records),
        container=_el_label(container),
        child_signature="dt/dd",
        max_depth=max_depth,
    )


def extract_records(html: str, base_url: str = "") -> RecordSet | None:
    """Locate the dominant repeated record region and extract its records.

    Args:
        html: The page HTML to mine.
        base_url: When given, resolves relative hrefs to absolute URLs.

    Returns:
        A `RecordSet` of the located region, or `None` when no signature clears
        the detection guards — an article, a near-empty JS shell, a reference
        doc. The caller treats `None` as "this page is not a listing; fall
        through to the next extraction source".
    """
    if not html or not html.strip():
        return None
    tree = _parse_tree(html, base_url)
    if tree is None:
        return None

    groups = _group_signatures(tree)

    candidates: list[_Candidate] = []
    for sig, members in groups.items():
        candidate = _evaluate(sig, members)
        if candidate is not None:
            candidates.append(candidate)

    chosen = _select(candidates)
    if chosen is None:
        # Signature detection found nothing. Before falling through, try the one
        # shape it is structurally unable to see: a definition list. Ordered as a
        # FALLBACK, not a competing candidate, so no page that already yields a
        # region can change what it yields — a class-based listing on a page that
        # also carries a `<dl>` glossary still wins, which is correct.
        region = _definition_list_region(tree)
        if region is not None:
            return _build_definition_record_set(*region)
        return None

    return _build_record_set(chosen)
