"""A pytest plugin for one collection run: says which of the lanes `serial` and `quarantine` the selected tests use."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

PREFIX = "any-gate-markers:"
LANES = ("serial", "quarantine")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Print `any-gate-markers: serial quarantine` naming the lanes some selected test is marked for."""
    seen = [lane for lane in LANES if any(item.get_closest_marker(lane) for item in items)]
    sys.stdout.write(f"{PREFIX} {' '.join(seen)}\n")
