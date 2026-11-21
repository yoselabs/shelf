"""Test double: time the test moves by hand, usable as `Host.clock` and `Host.sleep`."""

from __future__ import annotations


class ManualClock:
    """One number for wall and monotonic time. Calling it reads it; `sleep` advances it instead of waiting."""

    def __init__(self, now: float = 1_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds
