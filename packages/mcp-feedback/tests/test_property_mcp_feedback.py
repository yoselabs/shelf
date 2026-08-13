"""Property-based tests for the pure description-building logic.

See docs/runbooks/property-based-testing.md. `_build_description` is the one
pure function in this package worth property-testing — tool registration
itself is async FastMCP glue, out of scope per the runbook's "when to skip"
list.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from mcp_feedback._tool import _BASE_DESCRIPTION, _build_description

_TEXT = st.text(min_size=1, max_size=200)


@given(extra=_TEXT)
@settings(max_examples=200)
def test_property_extra_instructions_appends_never_replaces(extra: str) -> None:
    """For any non-empty extra_instructions, the base description survives
    verbatim as a prefix-containing substring, and the extra text is also
    present — appended, not swapped in.
    """
    out = _build_description(extra)
    assert _BASE_DESCRIPTION in out
    assert extra in out


@given(extra=st.one_of(st.none(), st.just("")))
@settings(max_examples=10)
def test_property_missing_or_empty_extra_leaves_only_base(extra: str | None) -> None:
    assert _build_description(extra) == _BASE_DESCRIPTION
