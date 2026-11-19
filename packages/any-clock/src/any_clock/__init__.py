"""A nested phase stopwatch (one phase owns each instant, totals add up to wall time) and the stored UTC stamp."""

from any_clock.clock import PhaseClock
from any_clock.stamp import parse_stamp, utc_stamp

__all__ = ["PhaseClock", "parse_stamp", "utc_stamp"]
