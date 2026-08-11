"""Property-based tests for the pure projection/pagination core of ListViewMiddleware.

See docs/runbooks/property-based-testing.md. Targets `_project_row` / `_apply_to_items`
directly — the middleware class itself (`ListViewMiddleware`) is async FastMCP glue,
out of scope per the runbook's "when to skip" list; these two functions are where the
actual list-shaping logic (and its invariants) live.
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st
from mcp_result_wire._list_view import ListViewSettings, _apply_to_items, _project_row

_KEY = st.text(alphabet=st.characters(categories=["L", "N"]), min_size=1, max_size=6)
_VALUE = st.one_of(st.integers(), st.text(max_size=20), st.none(), st.booleans())
_ROW = st.dictionaries(_KEY, _VALUE, max_size=6)


@given(row=_ROW, fields=st.lists(_KEY, max_size=6))
@settings(max_examples=200)
def test_property_projected_row_keys_are_exactly_fields_present_in_row(row: dict, fields: list[str]) -> None:
    """No key outside `fields` ever survives; no key in `fields` but absent from
    the row is invented — for any row and any field list, not the one hand-shape
    this middleware happens to be used with today.
    """
    out = _project_row(row, tuple(fields))
    assert set(out) == set(fields) & set(row)


@given(row=_ROW, fields=st.lists(_KEY, min_size=1, max_size=6))
@settings(max_examples=200)
def test_property_projected_values_are_unchanged(row: dict, fields: list[str]) -> None:
    """A kept field's value is untouched — projection only removes keys, it never
    transforms a value.
    """
    out = _project_row(row, tuple(fields))
    for k, v in out.items():
        assert v == row[k]


@given(row=st.one_of(st.integers(), st.text(), st.none(), st.lists(st.integers())))
@settings(max_examples=50)
def test_property_non_dict_row_passes_through_untouched(row: Any) -> None:
    """A row that isn't a dict (already-projected, or a scalar in a mixed list)
    passes through unchanged rather than raising.
    """
    assert _project_row(row, ("a", "b")) is row


@given(
    items=st.lists(_ROW, max_size=20),
    page_size=st.one_of(st.none(), st.integers(min_value=0, max_value=30)),
)
@settings(max_examples=200)
def test_property_pagination_never_exceeds_page_size_and_is_a_prefix(items: list[dict], page_size: int | None) -> None:
    """For any list and any page_size: the result length never exceeds page_size
    (when set and positive), and the surviving items are exactly a PREFIX of the
    input in original order — pagination never reorders or drops from the middle.
    """
    out = _apply_to_items(items, ListViewSettings(page_size=page_size))
    if page_size is not None and page_size > 0:
        assert len(out) <= page_size
        assert out == items[:page_size]
    else:
        assert out == items
