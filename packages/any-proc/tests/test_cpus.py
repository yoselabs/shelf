"""The CPUs a process may use: affinity or core count, capped by a cgroup quota (moved from a2kay tests/services/search/test_embed.py)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import any_proc.cpus as ac
import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("files", "host", "expected"),
    [
        pytest.param({}, 8, 8, id="no-cgroup-files"),
        pytest.param({"cpu.max": "max 100000\n"}, 8, 8, id="v2-unlimited"),
        pytest.param({"cpu.max": "200000 100000\n"}, 16, 2, id="v2-two-cpus"),
        pytest.param({"cpu.max": "150000 100000\n"}, 16, 2, id="v2-one-and-a-half-rounds-up"),
        pytest.param({"cpu.max": "50000 100000\n"}, 16, 1, id="v2-half-a-cpu-is-one"),
        pytest.param({"cpu.max": "800000 100000\n"}, 4, 4, id="v2-quota-above-the-host"),
        pytest.param({"cpu.max": "200000 0\n"}, 8, 8, id="v2-zero-period-is-no-quota"),
        pytest.param({"cpu/cpu.cfs_quota_us": "300000\n", "cpu/cpu.cfs_period_us": "100000\n"}, 16, 3, id="v1-three-cpus"),
        pytest.param({"cpu.cfs_quota_us": "100000\n", "cpu.cfs_period_us": "100000\n"}, 16, 1, id="v1-flat-at-the-root"),
        pytest.param({"cpu,cpuacct/cpu.cfs_quota_us": "200000\n", "cpu,cpuacct/cpu.cfs_period_us": "100000\n"}, 16, 2, id="v1-cpu-cpuacct"),
        pytest.param({"cpu/cpu.cfs_quota_us": "-1\n", "cpu/cpu.cfs_period_us": "100000\n"}, 8, 8, id="v1-unlimited"),
        pytest.param({"cpu.max": "garbage"}, 8, 8, id="unreadable-quota-is-no-quota"),
    ],
)
def test_the_cpus_a_container_may_use_are_its_cgroup_quota_not_the_hosts_cores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: dict[str, str], host: int, expected: int
) -> None:
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        _ = (tmp_path / name).write_text(text, encoding="utf-8")
    monkeypatch.setattr(ac, "host_cpus", lambda: host)
    assert ac.available_cpus(tmp_path) == expected


def test_the_default_cgroup_directory_is_the_module_attribute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ = (tmp_path / "cpu.max").write_text("200000 100000\n", encoding="utf-8")
    monkeypatch.setattr(ac, "host_cpus", lambda: 16)
    monkeypatch.setattr(ac, "CGROUP_DIR", tmp_path)
    assert ac.available_cpus() == 2


def test_the_host_cpus_are_the_affinity_when_there_is_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("os.sched_getaffinity", lambda _pid: {0, 1, 2}, raising=False)
    assert ac.host_cpus() == 3


def test_the_host_cpus_are_the_core_count_where_the_os_has_no_affinity(monkeypatch: pytest.MonkeyPatch) -> None:
    """macOS and Windows have no `os.sched_getaffinity`."""
    monkeypatch.delattr("os.sched_getaffinity", raising=False)
    monkeypatch.setattr("os.cpu_count", lambda: 6)
    assert ac.host_cpus() == 6
    monkeypatch.setattr("os.cpu_count", lambda: None)
    assert ac.host_cpus() == 1


def test_a_refused_affinity_falls_back_to_the_core_count(monkeypatch: pytest.MonkeyPatch) -> None:
    def refused(_pid: int) -> set[int]:
        raise OSError

    monkeypatch.setattr("os.sched_getaffinity", refused, raising=False)
    monkeypatch.setattr("os.cpu_count", lambda: 4)
    assert ac.host_cpus() == 4


def test_cpus_reads_what_the_process_was_given(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ = (tmp_path / "cpu.max").write_text("150000 100000\n", encoding="utf-8")
    monkeypatch.setattr(ac, "host_cpus", lambda: 16)
    cpus = ac.Cpus.read(tmp_path)
    assert (cpus.host, cpus.quota, cpus.available) == (16, 2, 2)
    assert ac.Cpus(host=4).available == 4
