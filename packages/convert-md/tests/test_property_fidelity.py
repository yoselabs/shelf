"""Property-based tests, additive on top of the calibrated-threshold example suite.

See docs/runbooks/property-based-testing.md. `fidelity.py`'s own docstring states
calibrated numeric thresholds (0.02 garbage density, 0.03 cid-leak fraction, 0.35
shattered-table fraction) derived from a real bench corpus — the example suite
checks specific real conversion outputs against those thresholds; this generalizes
the threshold *boundaries themselves* to arbitrary constructed inputs, which the
real-corpus examples can't parametrically sweep.
"""

from __future__ import annotations

from convert_md.fidelity import grade
from hypothesis import given, settings
from hypothesis import strategies as st

_WHITESPACE_ONLY = st.text(alphabet=" \t\n\r", max_size=50)
_CLEAN_TEXT = st.text(alphabet=st.characters(categories=["L", "N"], max_codepoint=0x2FF), min_size=1, max_size=500)


@given(text=_WHITESPACE_ONLY)
@settings(max_examples=100)
def test_property_whitespace_only_output_is_always_failed(text: str) -> None:
    """Generalizes the one empty-string example across any whitespace mix
    (spaces, tabs, newlines, or none at all)."""
    assert grade(markdown=text, source_size=100) == ("failed", ["all"], ["empty_output"])


@given(
    garbage_count=st.integers(min_value=1, max_value=50),
    clean_count=st.integers(min_value=0, max_value=50),
)
@settings(max_examples=100)
def test_property_garbage_density_above_threshold_is_always_partial(garbage_count: int, clean_count: int) -> None:
    """For any construction where the garbage-character fraction provably
    exceeds the calibrated 0.02 threshold, the verdict is always partial with
    "encoding" flagged — not just the one hand-picked garbled document.
    """
    # \x01 is one of _GARBAGE_RE's matched control bytes; "a" never matches it.
    markdown = ("\x01" * garbage_count) + ("a" * clean_count)
    density = garbage_count / len(markdown)
    if density > 0.02:
        verdict, lost, _warnings = grade(markdown=markdown, source_size=len(markdown) * 10, check_yield=False)
        assert verdict == "partial"
        assert "encoding" in lost


@given(text=_CLEAN_TEXT)
@settings(max_examples=150)
def test_property_clean_short_text_always_grades_high(text: str) -> None:
    """For any non-empty, garbage-free, cid-free text short enough to stay
    under the structure-check's large-document threshold, with check_yield
    disabled (so this isolates the garbage/cid/shatter checks specifically,
    not yield), the grade is always high — generalizing beyond one clean
    example to the whole space of "boring, well-behaved" input.
    """
    verdict, lost, warnings = grade(markdown=text, source_size=100, check_yield=False)
    assert verdict == "high"
    assert lost == []
    assert warnings == []
