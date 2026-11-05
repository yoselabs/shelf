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
    `root`, so no instant is unowned and `sum(totals().values()) == wall()` (both share one clock read). The clock cannot stop a caller
    entering the wrong phase. Not thread-safe: `phase()` or `book()` from a thread other than the creating one raises.
    """

    def __init__(
        self,
        now: Callable[[], float],
        limits: Mapping[str, float] | None = None,
        *,
        root: str = "run",
        exempt: Iterable[str] = (),
        budget: float | None = None,
    ) -> None:
        self._now = now
        self._limits = dict(limits or {})
        self._exempt = frozenset(exempt)
        self._budget = budget
        self._owner = threading.get_ident()
        self._t0 = self._last = now()
        self._stack = [root]
        self._totals = {root: 0.0}

    def _book(self) -> float:
        """Book the time since the last read to the owning phase; returns the high-water clock reading.

        A clock stepping back is ignored until it passes its old high-water mark, so nothing is booked twice.
        """
        t = max(self._now(), self._last)
        self._totals[self._stack[-1]] += t - self._last
        self._last = t
        return t

    def _check_thread(self, caller: str) -> None:
        if threading.get_ident() != self._owner:
            msg = f"PhaseClock is single-threaded: {caller}() called from another thread"
            raise RuntimeError(msg)

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        """Own the time inside the block; the surrounding phase pauses. Leaves cleanly on an exception."""
        self._check_thread("phase")
        self._book()
        self._stack.append(name)
        self._totals.setdefault(name, 0.0)
        try:
            yield
        finally:
            try:
                self._book()
            finally:
                self._stack.pop()

    def book(self, phase: str, seconds: float) -> float:
        """Move already-measured `seconds` from the innermost open phase (the donor) into `phase`; returns what moved.

        For time the caller measured itself, after the fact, where a `phase()` block cannot wrap it. The donor is
        `current()` at call time, so the moved seconds were being counted there and `sum(totals().values())` stays
        `wall()`. The move is capped at the donor's total so no total goes negative; a negative, zero or NaN `seconds`
        moves nothing, and booking into the donor itself moves nothing (returns 0.0). A booked exempt phase lowers
        `charged()`; a booked limited phase can make `over()` report it. Same single-thread rule as `phase()`.
        """
        self._check_thread("book")
        self._book()
        donor = self._stack[-1]
        if phase == donor or not seconds > 0:
            return 0.0
        moved = min(seconds, self._totals[donor])
        self._totals[donor] -= moved
        self._totals[phase] = self._totals.get(phase, 0.0) + moved
        return moved

    def current(self) -> str:
        return self._stack[-1]

    def wall(self) -> float:
        return self._book() - self._t0

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
        """`(phase, spent, limit)` for each limited phase past its limit, then `("charged", spent, budget)` when
        `charged()` is past `budget`; empty while inside."""
        totals = self.totals()
        found = [(name, totals.get(name, 0.0), cap) for name, cap in self._limits.items() if totals.get(name, 0.0) > cap]
        spent = sum(s for name, s in totals.items() if name not in self._exempt)
        if self._budget is not None and spent > self._budget:
            found.append(("charged", spent, self._budget))
        return found
