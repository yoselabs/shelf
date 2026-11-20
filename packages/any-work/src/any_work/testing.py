"""Test double: time the test moves by hand, usable as `clock=` for `Work` and `drain` and `sleep=` for `drain`."""

from __future__ import annotations


class ManualClock:
    """Wall and monotonic time in one number. Calling it reads it; ``sleep`` advances it instead of waiting."""

    def __init__(self, now: float = 1_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds
