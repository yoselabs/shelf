"""Property-based tests, additive on top of the example suite.

See docs/runbooks/property-based-testing.md. Targets `render_record`'s three
numeric contracts stated in module-level constants (`_MAX_RECORD_CHARS`,
`_MAX_LINKS_PER_RECORD`, the depth-indent scheme) — each currently checked at one
or two hand-picked depths/lengths, generalized here to arbitrary values.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from record_mine.models import Record, RecordSet
from record_mine.render import render_record

_TEXT = st.text(max_size=800)
# Alphanumeric only: a generated anchor/href containing the "·" separator itself
# would make a naive occurrence-count ambiguous between content and structure.
_SAFE_WORD = st.text(alphabet=st.characters(categories=["L", "N"]), min_size=1, max_size=20)
_LINK = st.tuples(_SAFE_WORD, _SAFE_WORD)


@given(text=_TEXT, depth=st.integers(min_value=0, max_value=6))
@settings(max_examples=150)
def test_property_text_led_row_is_indented_by_exactly_two_spaces_per_depth(text: str, depth: int) -> None:
    """For any depth, the rendered line's leading whitespace is exactly `2 * depth`
    spaces — not "roughly indented," an exact count.
    """
    out = render_record(text, (), depth)
    first_line = out.split("\n")[0]
    leading = len(first_line) - len(first_line.lstrip(" "))
    assert leading == 2 * depth


@given(text=_TEXT, depth=st.integers(min_value=0, max_value=3))
@settings(max_examples=150)
def test_property_text_led_row_never_exceeds_max_record_chars(text: str, depth: int) -> None:
    """The truncation bound is a real contract (`_MAX_RECORD_CHARS = 500`), for
    any input length, not just the one long-string example.
    """
    out = render_record(text, (), depth)
    body_line = out.split("\n")[0]
    # strip the "{indent}- " prefix to isolate the truncated text itself
    prefix = "  " * depth + "- "
    assert len(body_line) - len(prefix) <= 500


@given(links=st.lists(_LINK, max_size=20), depth=st.integers(min_value=0, max_value=2))
@settings(max_examples=150)
def test_property_never_more_than_ten_links_rendered(links: list[tuple[str, str]], depth: int) -> None:
    """`_MAX_LINKS_PER_RECORD = 10` — for any number of generated links, the
    rendered link line never shows more than 10, even though `Record.links`
    itself (not exercised here) is documented to keep all of them.
    """
    out = render_record("text", tuple(links), depth)
    if links:
        link_line = out.split("\n")[-1]
        # Each rendered link contributes exactly one "[" — robust regardless of
        # generated anchor/href content, unlike counting the " · " separator.
        assert link_line.count("[") <= 10


@given(n_records=st.integers(min_value=0, max_value=10), max_depth=st.integers(min_value=0, max_value=5))
@settings(max_examples=100)
def test_property_to_markdown_header_matches_record_count_and_threading(n_records: int, max_depth: int) -> None:
    """The header's count and label always match the actual record set, for any
    generated count and threading depth — not just the one flat and one
    threaded example.
    """
    records = tuple(
        Record(text=f"t{i}", links=(), heading_text=None, heading_link=None, depth=0, markdown=f"- t{i}") for i in range(n_records)
    )
    rs = RecordSet(records=records, container="c", child_signature="s", max_depth=max_depth)
    md = rs.to_markdown()
    header = md.split("\n", 1)[0]
    assert f"({n_records} " in header
    if max_depth > 0:
        assert "Discussion" in header and "comments" in header
    else:
        assert "Listing" in header and "records" in header
