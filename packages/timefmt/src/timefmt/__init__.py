"""timefmt — one adaptive duration formatter, so a duration string reads the same everywhere.

**Stop hand-formatting durations.** ``fmt_dur(ms)`` is the single place a
millisecond count becomes a human string: sub-second stays integer milliseconds,
low seconds carry one decimal, whole seconds drop the decimal, and a minute or
more renders ``{m}m{ss}s``. The unit tracks the magnitude, so no reading wastes
precision and every duration in a codebase looks alike.

Zero-dependency and domain-free — integer in, string out; the *policy* for where a
duration appears lives above this primitive.
"""

from __future__ import annotations

__all__ = ["fmt_dur"]


def fmt_dur(ms: int) -> str:
    """Format ``ms`` (integer milliseconds) per the four-tier rule.

    Args:
        ms: A duration in whole milliseconds.

    Returns:
        A magnitude-matched string:

        - ``< 1000`` -> ``"{ms}ms"`` (integer, never ``"0.0s"`` for zero)
        - ``1000 <= ms < 7000`` -> ``"{s:.1f}s"`` (one decimal)
        - ``7000 <= ms < 60_000`` -> ``"{s}s"`` (integer)
        - ``>= 60_000`` -> ``"{m}m{s:02d}s"``
    """
    if ms < 1000:
        return f"{ms}ms"
    if ms < 7000:
        return f"{ms / 1000:.1f}s"
    if ms < 60_000:
        return f"{ms // 1000}s"
    minutes, sec = divmod(ms // 1000, 60)
    return f"{minutes}m{sec:02d}s"
