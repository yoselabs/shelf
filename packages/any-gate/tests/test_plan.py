"""Sizing a test run to its work: few tests run in one process, many spread over workers the box can afford."""

from __future__ import annotations

import os

import pytest
from any_gate import Resources, detect, plan, too_wide, workers
from stream_proc.capture import Captured


@pytest.mark.parametrize(
    ("tests", "cpus", "ram_gb", "expected"),
    [
        (0, 8, 16, 1),
        (1, 8, 16, 1),
        (150, 8, 16, 1),  # a small selection costs more to spread than to run
        (151, 8, 16, 2),
        (400, 8, 16, 3),
        (5000, 8, 16, 4),  # the default cap: one run must leave the box to the others
        (5000, 2, 16, 2),  # never more workers than cores
        (5000, 8, 6, 3),  # nor more than the memory feeds (2 GB each)
        (5000, 8, 1, 1),
    ],
)
def test_a_run_uses_the_fewest_workers_its_work_the_cores_and_the_memory_allow(tests: int, cpus: int, ram_gb: float, expected: int) -> None:
    assert workers(tests, Resources(cpus=cpus, ram_gb=ram_gb)) == expected


def test_the_cap_and_the_size_of_a_worker_are_the_callers_to_change() -> None:
    assert workers(5000, Resources(cpus=14, ram_gb=64), cap=12) == 12
    assert workers(5000, Resources(cpus=14, ram_gb=64), cap=14, per_worker_tests=1000) == 5


@pytest.mark.parametrize(
    ("selected", "total", "wide"), [(0, 0, False), (49, 100, False), (50, 100, False), (51, 100, True), (100, 100, True)]
)
def test_a_selection_over_half_of_everything_is_too_wide(selected: int, total: int, wide: bool) -> None:
    assert too_wide(selected, total) is wide


def test_a_box_without_available_pages_reports_the_memory_vm_stat_calls_free(monkeypatch: pytest.MonkeyPatch) -> None:
    # macOS has no SC_AVPHYS_PAGES; every gate run there died in detect() before this.
    vm_stat = "Pages free: 100.\nPages inactive: 50.\nPages speculative: 10.\nPages active: 999999.\n"
    monkeypatch.setattr(os, "sysconf_names", {"SC_PAGE_SIZE": 0})
    monkeypatch.setattr(os, "sysconf", lambda name: 16384)
    monkeypatch.setattr(plan, "capture", lambda *a, **k: Captured(0, vm_stat.encode(), b"", 0.0, False))
    assert detect().ram_gb == pytest.approx(160 * 16384 / 1024**3)
