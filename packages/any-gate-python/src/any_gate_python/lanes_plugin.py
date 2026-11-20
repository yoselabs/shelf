"""A pytest plugin for the stages: reports what was selected, and keeps only one lane's tests.

A lane is `serial` (marked `serial`, not `quarantine`), `quarantine` (marked `quarantine`) or `parallel` (neither). Selecting by lane here,
not by `-m`, leaves the repo's own `-m` default (`addopts = -m "not browser"`) in force: a second `-m` would replace it. The plugin runs
last, after `-m` has deselected, so its count and its lanes describe exactly what the stage would run.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.config.argparsing import Parser

PREFIX = "any-gate-collected:"
LANES = ("serial", "quarantine")


def lane_of(item: pytest.Item) -> str:
    """The lane a test runs in."""
    if item.get_closest_marker("quarantine"):
        return "quarantine"
    return "serial" if item.get_closest_marker("serial") else "parallel"


def pytest_addoption(parser: Parser) -> None:
    parser.addoption("--any-gate-lane", choices=("parallel", *LANES), default=None, help="run only this lane's tests")
    parser.addoption("--any-gate-report", action="store_true", default=False, help="print the selected count and the lanes in use")


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: Config, items: list[pytest.Item]) -> None:
    """Keep one lane's tests; with `--any-gate-report` print `any-gate-collected: <count> serial quarantine`."""
    lane = config.getoption("--any-gate-lane")
    if lane:
        kept = [item for item in items if lane_of(item) == lane]
        dropped = [item for item in items if lane_of(item) != lane]
        if dropped:
            config.hook.pytest_deselected(items=dropped)
        items[:] = kept
    if config.getoption("--any-gate-report"):
        seen = [name for name in LANES if any(lane_of(item) == name for item in items)]
        sys.stdout.write(f"{PREFIX} {len(items)} {' '.join(seen)}\n")
