"""PhaseClock: a stack of named phases over an injected clock."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping


class PhaseClock:
    """Time attributed to named phases; the innermost open phase owns the current instant.

    Entering a phase pauses the one around it; leaving resumes it. Time outside every `phase()` block belongs to
    `root`, so no instant is unowned and `sum(totals().values()) == wall()`. The clock cannot stop a caller
    entering the wrong phase. Not thread-safe: `phase()` from a thread other than the creating one raises.
    """

    def __init__(
        self,
        now: Callable[[], float],
        limits: Mapping[str, float] | None = None,
        *,
        root: str = "run",
        exempt: Iterable[str] = (),
    ) -> None:
        self._now = now
        self._limits = dict(limits or {})
        self._exempt = frozenset(exempt)
        self._owner = threading.get_ident()
        self._t0 = self._last = now()
        self._stack = [root]
        self._totals = {root: 0.0}

    def _book(self) -> None:
        t = self._now()
        self._totals[self._stack[-1]] += max(t - self._last, 0.0)  # a clock stepping back books nothing
        self._last = t

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        """Own the time inside the block; the surrounding phase pauses. Leaves cleanly on an exception."""
        if threading.get_ident() != self._owner:
            msg = "PhaseClock is single-threaded: phase() called from another thread"
            raise RuntimeError(msg)
        self._book()
        self._stack.append(name)
        self._totals.setdefault(name, 0.0)
        try:
            yield
        finally:
            self._book()
            self._stack.pop()

    def current(self) -> str:
        return self._stack[-1]

    def wall(self) -> float:
        return self._now() - self._t0

    def total(self, name: str) -> float:
        """Seconds owned by `name` so far, live while it is open; 0 for a phase never entered."""
        self._book()
        return self._totals.get(name, 0.0)

    def totals(self) -> dict[str, float]:
        self._book()
        return dict(self._totals)

    def charged(self) -> float:
        """Seconds owned by every phase that is not exempt."""
        return sum(s for name, s in self.totals().items() if name not in self._exempt)

    def over(self) -> list[tuple[str, float, float]]:
        """`(phase, spent, limit)` for each limited phase past its limit; empty while inside."""
        totals = self.totals()
        return [(name, totals.get(name, 0.0), cap) for name, cap in self._limits.items() if totals.get(name, 0.0) > cap]
