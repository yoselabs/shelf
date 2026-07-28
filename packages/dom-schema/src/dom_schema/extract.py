"""Apply a `Schema` to a page and report WHY it yielded what it yielded."""

from __future__ import annotations

from selectolax.parser import HTMLParser, Node

from .models import Extraction, Field, Schema, Yield


def _value(node: Node, spec: Field) -> str | None:
    target = node if spec.css == "." else node.css_first(spec.css)
    if target is None:
        return None
    raw = target.attributes.get(spec.attr) if spec.attr else target.text()
    if raw is None:
        return None
    if spec.strip_prefix and raw.lstrip().startswith(spec.strip_prefix):
        raw = raw.lstrip()[len(spec.strip_prefix) :]
    value = " ".join(raw.split())
    return value or None


def _row_values(halves: tuple[Node, ...], schema: Schema) -> tuple[dict[str, str], list[str]]:
    row: dict[str, str] = {}
    missing: list[str] = []
    for name, spec in schema.fields.items():
        found = next((v for v in (_value(h, spec) for h in halves) if v is not None), None)
        if found is None:
            if spec.required:
                missing.append(name)
            continue
        row[name] = found
    return row, missing


def extract(html: str, schema: Schema) -> Extraction:
    """Apply `schema` to `html`.

    Returns an `Extraction` whose `verdict` separates the three outcomes a bare
    row list conflates:

    - `OK`    — the container matched and rows came out.
    - `EMPTY` — the container matched and held nothing. A fact about the PAGE.
    - `ROT`   — the container did not match. A fact about the SCHEMA.

    That split is the package. A caller that only sees `len(rows) == 0` cannot
    tell an empty listing from selectors that stopped matching, so it reports
    "nothing here" either way — and a rotted parser goes on producing that
    answer indefinitely, with nothing to notice it.

    The distinction is only available because `Schema` is two-level. A flat
    selector cannot supply it, which is why `container` is required rather than
    optional.
    """
    tree = HTMLParser(html)
    container = tree.css_first(schema.container)
    if container is None:
        return Extraction(verdict=Yield.ROT)

    primaries = container.css(schema.row)
    if not primaries:
        return Extraction(verdict=Yield.EMPTY)

    seconds = container.css(schema.pair_with) if schema.pair_with else ()
    rows: list[dict[str, str]] = []
    missing: dict[str, int] = {}
    for i, primary in enumerate(primaries):
        halves = (primary, seconds[i]) if i < len(seconds) else (primary,)
        row, absent = _row_values(halves, schema)
        for name in absent:
            missing[name] = missing.get(name, 0) + 1
        if row:
            rows.append(row)

    if not rows:
        # Rows existed structurally but every declared field came back empty —
        # the container is right and the field selectors are not. Reporting this
        # as EMPTY would blame the page for the schema's failure.
        return Extraction(verdict=Yield.ROT, missing=missing)

    return Extraction(verdict=Yield.OK, rows=tuple(rows), missing=missing)
