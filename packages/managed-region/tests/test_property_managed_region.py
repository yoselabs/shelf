"""Property-based tests, additive on top of the example suite.

See docs/runbooks/property-based-testing.md. `replace_region`'s own name states its
invariants (idempotent, prose-preserving) plainly, which makes it an unusually clean
PBT target — but per the runbook's failure mode #2, generated body/content text has
to be filtered so it never accidentally contains the marker substrings themselves
(that's an explicitly out-of-contract input per the package's own docstring: markers
inside content need the caller's `escape`, tested separately below).
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from managed_region import replace_region

S = "<<S>>"
E = "<<E>>"

# Text that provably cannot contain a marker substring — the precondition the
# package's docstring states for calling without `escape`.
_SAFE_TEXT = st.text(max_size=200).filter(lambda t: S not in t and E not in t)


@given(body=_SAFE_TEXT, content=_SAFE_TEXT)
@settings(max_examples=200)
def test_property_idempotent_for_any_body_and_content(body: str, content: str) -> None:
    """Generalizes test_idempotent_same_content: re-applying with the SAME content
    is a no-op, for any marker-free body and content, not just one fixed pair.
    """
    once = replace_region(body, content, start_marker=S, end_marker=E)
    twice = replace_region(once, content, start_marker=S, end_marker=E)
    assert once == twice


@given(body=_SAFE_TEXT, content=_SAFE_TEXT)
@settings(max_examples=200)
def test_property_always_exactly_one_marker_pair(body: str, content: str) -> None:
    """The document always holds exactly one marker pair after any single call —
    whether it appended a new region or replaced an existing one.
    """
    out = replace_region(body, content, start_marker=S, end_marker=E)
    assert out.count(S) == 1
    assert out.count(E) == 1


@given(prose=_SAFE_TEXT, content1=_SAFE_TEXT, content2=_SAFE_TEXT)
@settings(max_examples=200)
def test_property_prose_before_region_survives_a_replace(prose: str, content1: str, content2: str) -> None:
    """Prose that existed before the marker pair survives byte-for-byte through a
    SECOND call that replaces the region's content — generalizes
    test_replaces_in_place_preserving_outside beyond one hand-picked prose string.
    """
    if prose.strip() == "":
        return  # the empty-body branch is a different code path, covered separately
    first = replace_region(prose, content1, start_marker=S, end_marker=E)
    second = replace_region(first, content2, start_marker=S, end_marker=E)
    assert prose.rstrip("\n") in second
    assert second.index(prose.rstrip("\n")) < second.index(S)


@given(content=st.text(max_size=100))
@settings(max_examples=200)
def test_property_escaped_content_never_creates_a_second_pair(content: str) -> None:
    """The security-relevant property named in the docstring but not example-tested
    for arbitrary content: with `escape` applied, injecting content that contains
    real marker substrings can never produce more than one real pair — for ANY
    generated content, not just the one hand-built poison string in the example
    suite.
    """

    def escape(text: str) -> str:
        return text.replace(S, "<<S_>>").replace(E, "<<E_>>")

    out = replace_region("prose\n", content, start_marker=S, end_marker=E, escape=escape)
    assert out.count(S) == 1
    assert out.count(E) == 1
