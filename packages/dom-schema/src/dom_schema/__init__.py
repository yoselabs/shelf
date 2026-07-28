"""dom-schema — declared CSS extraction that says WHY it found nothing.

Site scrapers rot silently. A selector stops matching when a site changes its
markup, the parse returns zero rows, and every caller reads zero rows as "the
page is empty" — because a bare `list[Row]` cannot say anything else. Nothing
fails, nothing warns, and the parser goes on answering "nothing here" for as
long as no one checks by hand.

This package makes that outcome unrepresentable. A `Schema` is TWO-level —
a `container` and the `row`s inside it — and `extract` reports which level
failed:

    OK     container matched, rows came out
    EMPTY  container matched, held nothing   -> a fact about the PAGE
    ROT    container did not match           -> a fact about the SCHEMA

A flat selector cannot supply that distinction, which is why `container` is
required rather than optional.

Public surface: `extract(html, schema) -> Extraction`, plus the boundary types
`Schema`, `Field`, `Extraction`, `Yield`.
"""

from __future__ import annotations

from .extract import extract
from .models import Extraction, Field, Schema, Yield

__all__ = ("Extraction", "Field", "Schema", "Yield", "extract")
