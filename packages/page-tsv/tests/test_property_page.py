"""Property-based tests, additive on top of the example suite.

See docs/runbooks/property-based-testing.md. Targets `assemble_page_envelope`
directly — the pure serialization seam this package's hybrid encoding hinges on.
Checks the envelope survives untouched (JSON round-trip, not string-compare) and
the discriminator/shape contract the module docstring states.
"""

from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st
from page_tsv.page import assemble_page_envelope

_JSON_SCALAR = st.one_of(st.none(), st.booleans(), st.integers(), st.text(max_size=20))
_ENVELOPE = st.dictionaries(
    st.text(alphabet=st.characters(categories=["L"]), min_size=1, max_size=8).filter(lambda k: k != "items"),
    _JSON_SCALAR,
    max_size=5,
)
_ROW = st.dictionaries(st.text(alphabet=st.characters(categories=["L"]), min_size=1, max_size=8), _JSON_SCALAR, max_size=4)


@given(envelope=_ENVELOPE, rows=st.lists(_ROW, max_size=8))
@settings(max_examples=150)
def test_property_envelope_keys_survive_untouched_and_items_becomes_a_tsv_string(envelope: dict, rows: list[dict]) -> None:
    """For any envelope dict (without its own `items` key) and any row set: every
    original envelope key/value round-trips through the JSON encode/decode
    exactly, `items` becomes a string (never a list), and the discriminator is
    always set — independent of what's actually inside the rows.
    """
    columns = sorted({k for row in rows for k in row})
    out = assemble_page_envelope(envelope, rows, columns)
    decoded = json.loads(out)

    for key, value in envelope.items():
        assert decoded[key] == value
    assert decoded["_items_format"] == "tsv"
    assert isinstance(decoded["items"], str)


@given(rows=st.lists(_ROW, min_size=1, max_size=8))
@settings(max_examples=150)
def test_property_items_tsv_has_one_line_per_row_plus_header(rows: list[dict]) -> None:
    """The embedded TSV blob always has exactly len(rows) + 1 lines (header + one
    per row) — generalizes lean-wire's own line-count invariant through this
    package's envelope-assembly seam, not just the raw encoder.
    """
    columns = sorted({k for row in rows for k in row})
    out = assemble_page_envelope({}, rows, columns)
    decoded = json.loads(out)
    tsv = decoded["items"]
    assert tsv.endswith("\n")
    assert tsv.count("\n") == len(rows) + 1
    assert len(tsv[:-1].split("\n")) == len(rows) + 1
