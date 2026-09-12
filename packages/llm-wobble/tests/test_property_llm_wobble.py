"""Property-based tests, additive on top of the example suite.

See docs/runbooks/property-based-testing.md. `is_double_escaped` is a heuristic run
over every body a consumer accepts, so the property that matters is the one that
bounds its false positives: the example tests name a few shapes that must survive,
and these say *no* multi-line text at all can be caught, whatever is in it.

`strip_fenced_blocks` gets the complementary invariant — it is the inverse of the
parse funnel, and inverses are where a property suite earns its keep: text with no
fence in it must come back unchanged apart from the documented outer strip.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from llm_wobble import is_double_escaped, strip_fenced_blocks

# Text likely to trip a naive escape counter: the literal pairs, in quantity. Built by
# joining tokens rather than by `alphabet=`, which takes single characters only.
_ESCAPE_HEAVY = st.lists(st.sampled_from(["\\n", "\\t", "\\r", '\\"', "a", " "]), max_size=30).map("".join)


@given(before=_ESCAPE_HEAVY, after=_ESCAPE_HEAVY)
def test_a_real_line_break_anywhere_always_clears_it(before: str, after: str) -> None:
    """No text containing a real newline is ever flagged, however many escapes it holds.

    This is what makes the detector safe to run unconditionally. A document that
    explains escape sequences is written across real lines; so is every ordinary
    multi-line body. Both are immune by construction, not by luck.
    """
    assert is_double_escaped(f"{before}\n{after}") is False


@given(text=st.text(max_size=200))
def test_it_never_raises_and_always_answers(text: str) -> None:
    """Total over `str`. A detector that can raise is worse than no detector."""
    assert isinstance(is_double_escaped(text), bool)


@given(text=st.text(alphabet=st.characters(blacklist_characters="`"), max_size=200))
def test_text_with_no_fence_survives_stripping(text: str) -> None:
    """The inverse property: with nothing to remove, only the documented strip applies."""
    assert strip_fenced_blocks(text) == text.strip()
