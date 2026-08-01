"""The four encoder guards — each one a defect measured in a live consumer.

`encode_envelope` loops a STATIC field tuple over a payload that is not static.
Four things go wrong at that seam, and a2web hit every one of them in production
before owning a local copy of this encoder (`a2web/src/a2web/wire.py`). The
guards are promoted here so the next consumer does not pay again.

Each test names the harm, not the mechanism — a guard that only says "calls the
right function" cannot tell you what breaks when it is removed.

Ordering note: these are contract tests, so they assert on the emitted wire
bytes rather than on internals. That is deliberate — semver on `lean-wire` is
the wire-format version, and the same reasoning applies one level up here.
"""

from __future__ import annotations

import json
from typing import Any

from page_tsv import Page, encode_envelope, encode_page_tsv, encode_page_tsv_dict
from pydantic import BaseModel


class Row(BaseModel):
    id: int
    title: str


# --- guard 1: presence -------------------------------------------------------


def test_a_field_the_model_pruned_stays_pruned() -> None:
    """A conditional field the model omitted must not be resurrected.

    The field tuple is static; the payload is not. Looping the tuple and
    encoding unconditionally re-inserts every omitted key as the bare `"\\n"`
    empty marker PLUS a `_<name>_format` sidecar — so a model that carefully
    prunes five conditionals gets ten dead keys handed back to the agent, on
    every healthy response. Absence is the signal; the encoder must not
    overwrite it with a claim of emptiness.
    """
    payload = {"answer": "42"}  # `rows` was pruned by the model
    out = json.loads(encode_envelope(payload, ("rows",)))

    assert out == {"answer": "42"}, "a pruned field was resurrected by the encoder"
    assert "rows" not in out
    assert "_rows_format" not in out


def test_a_present_but_empty_field_still_encodes() -> None:
    """The presence guard keys on PRESENCE, not truthiness.

    A model that deliberately emits `[]` is saying "I looked and there was
    nothing" — a different claim from omitting the field, and the encoder must
    preserve the difference rather than collapsing both to absent.
    """
    out = json.loads(encode_envelope({"rows": []}, ("rows",)))

    assert out["_rows_format"] == "tsv"
    assert out["rows"] == "\n"


# --- guard 2: already a string -----------------------------------------------


def test_a_pre_encoded_tsv_string_is_not_blanked() -> None:
    """A field that arrives already TSV-encoded must survive.

    A model whose own serializer renders a field to TSV hands this encoder a
    finished STRING, not a list of rows. Testing only for `list`/`tuple` and
    falling through to `[]` overwrites that content with the empty marker: the
    caller is told "we looked and found nothing" about a field the producer had
    populated and encoded one layer down.

    In a2web that field was the off-page index, so the defect read as an honest
    "no onward links" on responses that had them.
    """
    pre_encoded = "id\ttitle\n1\tAlpha\n"
    out = json.loads(encode_envelope({"rows": pre_encoded}, ("rows",)))

    assert out["rows"] == pre_encoded, "populated pre-encoded content was overwritten"
    assert out["_rows_format"] == "tsv"


# --- guard 3: shape ----------------------------------------------------------


def test_one_untabulatable_field_does_not_void_the_whole_envelope() -> None:
    """`encode_tsv` raises on a row that is neither a model nor a dict.

    That is the correct contract for a codec — but an unguarded call means ONE
    such field aborts the encode for the ENTIRE envelope. Every other field
    loses its TSV rendering and its `_<name>_format` discriminator, and if the
    caller wraps this in a bare `except` (a2web inherited exactly that), the
    failure is invisible while being far from harmless.

    A list of `[level, text]` pairs is the real-world shape that did it: already
    lean, deliberately not a table. Leaving it as JSON is the honest outcome.
    """
    payload = {
        "headings": [[1, "Title"], [2, "Section"]],  # pairs — not tabulatable
        "rows": [{"id": 1, "title": "Alpha"}],
    }
    out = json.loads(encode_envelope(payload, ("headings", "rows")))

    assert out["headings"] == [[1, "Title"], [2, "Section"]], "untabulatable field should stay JSON"
    assert "_headings_format" not in out, "no discriminator for a field that did not become TSV"
    assert out["rows"] == "id\ttitle\n1\tAlpha\n", "a sibling field lost its encode"
    assert out["_rows_format"] == "tsv"


# --- guard 4: union columns --------------------------------------------------


def test_columns_are_the_union_of_every_row_not_just_the_first() -> None:
    """Rows are heterogeneous BY CONSTRUCTION, so `rows[0]` is not the schema.

    Any model that prunes empties or elides a field at its default emits rows
    with different key sets. Deriving the header from the first row alone
    therefore DELETES every key the first row happened to lack — silently, with
    no error and no short row.

    The live case: an `info`-severity hint elides `severity`, a `critical` one
    does not. An info hint sorted first produced a table with no `severity`
    column at all, so the loudest signal in the system reached the agent
    unmarked. Nothing about the output looked wrong.
    """
    rows = [
        {"code": "quiet"},  # severity elided at its default
        {"code": "loud", "severity": "critical"},
    ]
    out = json.loads(encode_envelope({"rows": rows}, ("rows",)))

    header, *lines = out["rows"].rstrip("\n").split("\n")
    assert header == "code\tseverity", f"severity was dropped from the header: {header!r}"
    assert lines == ["quiet\t", "loud\tcritical"], "a sparse row must widen, not shift"


def test_union_preserves_first_seen_order_across_rows() -> None:
    """Column order is first-seen, not sorted — declared field order is the
    contract `lean-wire` asks callers to preserve, and a later row's new key
    appends rather than reshuffling."""
    rows = [{"b": 1, "a": 2}, {"c": 3, "b": 4}]
    out = json.loads(encode_envelope({"rows": rows}, ("rows",)))

    assert out["rows"].split("\n")[0] == "b\ta\tc"


def test_the_page_dict_entrypoint_unions_its_columns_too() -> None:
    """Same rule on the page path — `items` is a table like any other.

    `encode_page_tsv_dict` is what a result middleware hits: by the time it runs
    the generic item type is gone, so columns are row-derived and every word of
    `_derive_columns`'s reasoning applies unchanged.
    """
    payload = {"items": [{"code": "quiet"}, {"code": "loud", "severity": "critical"}]}
    out = json.loads(encode_page_tsv_dict(payload))

    assert out["items"].split("\n")[0] == "code\tseverity"


def test_the_page_type_fallback_unions_its_columns_too() -> None:
    """The other row-derived path: `Page[T]` whose `T` is not a resolvable model.

    `_item_columns` prefers the declared item type — already a superset, already
    safe. It falls back to reading the items themselves for `Page[Any]` and bare
    `Page`, and that fallback had the identical first-row deletion bug.
    """
    page: Page[Any] = Page(items=[{"code": "quiet"}, {"code": "loud", "severity": "critical"}])
    out = json.loads(encode_page_tsv(page))

    assert out["items"].split("\n")[0] == "code\tseverity"


def test_the_typed_page_path_is_unchanged() -> None:
    """Anti-regression: a declared item type still yields declared field order,
    including a field every row happened to elide."""
    out = json.loads(encode_page_tsv(Page[Row](items=[Row(id=1, title="Alpha")])))

    assert out["items"] == "id\ttitle\n1\tAlpha\n"
    assert out["_items_format"] == "tsv"


def test_model_rows_still_use_declared_field_order() -> None:
    """The union rule must not regress the model path.

    A `BaseModel` row carries its declared order in its dump, so the union
    across model rows is that order — no behaviour change for the common case.
    """
    out = json.loads(encode_envelope({"rows": [Row(id=1, title="Alpha").model_dump()]}, ("rows",)))

    assert out["rows"] == "id\ttitle\n1\tAlpha\n"
