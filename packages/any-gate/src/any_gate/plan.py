"""Sizing a test run to its work: few tests run in one process, many spread over only as many workers as the box can afford."""

from __future__ import annotations

import math
import os
import re
import subprocess
from dataclasses import dataclass

__all__ = ["Resources", "detect", "too_wide", "workers"]

PER_WORKER_TESTS = 150
RAM_PER_WORKER_GB = 2.0
DEFAULT_CAP = 4
WIDE_SHARE = 0.5


@dataclass(frozen=True)
class Resources:
    """What this box can give one run."""

    cpus: int
    ram_gb: float


def detect() -> Resources:
    """The cores this process may use and the memory the box has free to give."""
    cpus = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)
    return Resources(cpus=cpus, ram_gb=_free_gb())


def _free_gb() -> float:
    size = os.sysconf("SC_PAGE_SIZE")
    if "SC_AVPHYS_PAGES" in os.sysconf_names:
        return os.sysconf("SC_AVPHYS_PAGES") * size / 1024**3
    out = subprocess.run(["vm_stat"], capture_output=True, text=True, check=False).stdout  # macOS has no SC_AVPHYS_PAGES
    pages = sum(int(m[1]) for m in re.finditer(r"Pages (?:free|inactive|speculative):\s+(\d+)", out))
    return pages * size / 1024**3


def workers(
    tests: int,
    resources: Resources,
    *,
    cap: int = DEFAULT_CAP,
    per_worker_tests: int = PER_WORKER_TESTS,
    ram_per_worker_gb: float = RAM_PER_WORKER_GB,
) -> int:
    """How many workers to run `tests` with; 1 means one process with no worker pool.

    The least of: the cores, the memory at `ram_per_worker_gb` each, one worker per `per_worker_tests` tests, and `cap`
    (a run must leave the box to the others). Never below 1.
    """
    wanted = math.ceil(tests / per_worker_tests)
    return max(1, min(resources.cpus, int(resources.ram_gb // ram_per_worker_gb), wanted, cap))


def too_wide(selected: int, total: int, *, share: float = WIDE_SHARE) -> bool:
    """Whether a selection is over `share` of everything: a sign the selector is reaching further than the change."""
    return total > 0 and selected / total > share
