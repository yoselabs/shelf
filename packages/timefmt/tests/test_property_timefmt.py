"""Property-based tests, additive on top of the boundary-exhaustive example suite.

See docs/runbooks/property-based-testing.md. test_timefmt.py already hand-covers
every tier boundary, so a naive "does it match the example tests" property would add
nothing (the runbook flags this package explicitly as lower marginal value for that
reason). What it does NOT cover: precision (does the embedded number, independently
recomputed, actually approximate ms?), and negative/undocumented input — fmt_dur's
docstring never states a precondition that ms >= 0.
"""

from __future__ import annotations

import re

from hypothesis import example, given, settings
from hypothesis import strategies as st
from timefmt import fmt_dur

_TIER_PATTERN = re.compile(
    r"^(?P<ms>\d+)ms$"
    r"|^(?P<s1>\d+\.\d)s$"
    r"|^(?P<s2>\d+)s$"
    r"|^(?P<m>\d+)m(?P<s3>\d{2})s$"
)


@given(ms=st.integers(min_value=0, max_value=10_000_000))
@settings(max_examples=300)
def test_property_output_always_matches_exactly_one_tier_shape(ms: int) -> None:
    """For any non-negative duration, the output matches exactly one of the four
    documented shapes — not zero, not an ad-hoc format the docstring doesn't name.
    """
    out = fmt_dur(ms)
    match = _TIER_PATTERN.match(out)
    assert match is not None, f"fmt_dur({ms}) = {out!r} matches none of the four documented shapes"


@given(ms=st.integers(min_value=0, max_value=10_000_000))
@example(ms=1450)  # exact half-tick: 1.45s -> "1.4s". Hypothesis found this; its example
# DB is self-gitignored, so pin the boundary here or it guards only the machine that hit it.
@settings(max_examples=300)
def test_property_embedded_number_approximates_ms_independently(ms: int) -> None:
    """Recompute what the embedded number *should* be from first principles (not by
    calling fmt_dur again) and check the string's own number is within that tier's
    stated precision — an independent check of the docstring's numeric claim, not a
    restatement of the implementation.
    """
    out = fmt_dur(ms)
    match = _TIER_PATTERN.match(out)
    assert match is not None
    if match.group("ms") is not None:
        assert int(match.group("ms")) == ms
    elif match.group("s1") is not None:
        # tier 2: one-decimal seconds. Half a tick (0.05s) is the *inclusive* bound —
        # an input landing exactly on a half-tick (ms=1450 -> "1.4s") is correctly
        # rounded, not an error, so a strict `<` would reject valid output. The epsilon
        # covers float representation only: abs(1.4 - 1.45) is 0.050000000000000044.
        assert abs(float(match.group("s1")) - ms / 1000) <= 0.05 + 1e-9
    elif match.group("s2") is not None:
        # tier 3: truncated (not rounded) whole seconds
        shown = int(match.group("s2"))
        assert shown * 1000 <= ms < (shown + 1) * 1000
    else:
        # tier 4: {m}m{ss}s — reconstruct total seconds and compare to floor(ms/1000)
        minutes, secs = int(match.group("m")), int(match.group("s3"))
        assert minutes * 60 + secs == ms // 1000


@given(ms=st.integers(min_value=-10_000_000, max_value=-1))
@settings(max_examples=100)
def test_property_negative_duration_does_not_crash(ms: int) -> None:
    """fmt_dur's docstring states no precondition that ms >= 0 — for any negative
    input, at minimum it must not raise. (What it *should* render for a negative
    duration is a separate, undocumented question this property does not answer;
    if this ever starts raising, that is the thing to resolve — silently, or by
    stating a precondition in the docstring.)
    """
    fmt_dur(ms)  # must not raise
