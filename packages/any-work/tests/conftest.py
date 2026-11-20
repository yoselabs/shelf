"""Shared fixtures: a manual clock and a Work built on a temp dir."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from any_work import Work
from any_work.testing import ManualClock

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock()


@pytest.fixture
def work(tmp_path: Path, clock: ManualClock) -> Iterator[Work]:
    # rand 0.5 makes the jitter factor exactly 1, so a retry is due after exactly base * 2**attempt.
    table = Work(
        tmp_path / "work.db", tmp_path / "leases", clock=clock, rand=lambda: 0.5, max_attempts=3, backoff_base=10.0, backoff_cap=100.0
    )
    yield table
    table.close()
