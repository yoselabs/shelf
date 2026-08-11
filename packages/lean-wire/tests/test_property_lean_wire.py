"""Property-based tests, additive on top of the golden-bytes example suite.

See docs/runbooks/property-based-testing.md. `_tsv.py`'s own docstring states two
invariants in words that the example suite only checks against hand-picked strings
(newline, tab, backslash, CR, each tested once): "a cell never contains a raw tab or
newline" and "the escaping is reversible." Both generalize cleanly to arbitrary
strings, which is exactly where a hand-written example suite runs out of budget.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from lean_wire import encode_tsv

_CELL_TEXT = st.text(max_size=200)  # any string, including backslashes/tabs/newlines/CR


def _unescape(text: str) -> str:
    """Reverse `_tsv._escape` by scanning, not by sequential `.replace()` — a naive
    reverse-order `.replace()` chain is exactly the kind of thing that looks right
    and silently mis-decodes a string like ``"\\\\n"`` (an escaped backslash
    followed by a literal ``n``, vs. an escaped newline). Independent of the
    source's own implementation on purpose — this is what "reversible" has to mean
    for a caller, not a mirror of how `_escape` happens to be written.
    """
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            mapping = {"\\": "\\", "t": "\t", "n": "\n", "r": "\r"}
            if nxt in mapping:
                out.append(mapping[nxt])
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


@given(cell=_CELL_TEXT)
@settings(max_examples=300)
def test_property_one_record_is_always_exactly_one_line(cell: str) -> None:
    """Generalizes test_one_record_is_exactly_one_line_even_with_multiline_cells:
    for ANY cell content, encoding one row never introduces more than the header
    line + one data line — no raw \\n from inside a cell escapes into the line count.
    """
    out = encode_tsv([{"v": cell}], columns=["v"])
    assert out.count("\n") == 2  # header\n + row\n
    assert out.endswith("\n")
    assert len(out[:-1].split("\n")) == 2  # strip exactly the trailing \n, not every one


@given(cell=_CELL_TEXT)
@settings(max_examples=300)
def test_property_a_tab_always_separates_exactly_the_declared_columns(cell: str) -> None:
    """For any content in one cell of a two-column row, splitting the data line on
    \\t yields exactly 2 parts — a raw tab inside the cell never masquerades as a
    column separator.
    """
    out = encode_tsv([{"a": cell, "b": "x"}], columns=["a", "b"])
    data_line = out.split("\n")[1]
    assert len(data_line.split("\t")) == 2


@given(cell=_CELL_TEXT)
@settings(max_examples=300)
def test_property_escaping_is_reversible(cell: str) -> None:
    """The docstring's explicit claim ("the escaping is reversible"), checked
    against an independent unescape implementation rather than assumed true
    because the forward direction has hand-picked examples.
    """
    out = encode_tsv([{"v": cell}], columns=["v"])
    data_line = out.split("\n")[1]
    assert _unescape(data_line) == cell
