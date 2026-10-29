"""The CPUs a process may really use.

``os.cpu_count()`` is the host's. Under a container limit (compose ``cpus: 2``) on a 16-core host a
thread count taken from it starts eight threads that spin-wait for two CPUs of quota.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

#: Where a container's CPU quota is written (cgroup v2: ``cpu.max``; v1: ``cpu.cfs_quota_us`` and ``cpu.cfs_period_us``).
CGROUP_DIR = Path("/sys/fs/cgroup")


def host_cpus() -> int:
    """The cores this process may be scheduled on: its affinity where the OS has one, else the machine's count."""
    affinity = getattr(os, "sched_getaffinity", None)  # absent on macOS and Windows
    try:
        if affinity is not None:
            return max(1, len(affinity(0)))
    except OSError:
        pass
    return os.cpu_count() or 1


def cgroup_quota(cgroup_dir: Path | None = None) -> int | None:
    """The container's CPU quota in whole CPUs, rounded up (1.5 is 2), or ``None`` for no quota.

    Missing, unlimited (``max``, ``-1``), zero-period or unreadable is no quota. cgroup v2 keeps it in
    ``cpu.max`` at the root; v1 in ``cpu/`` or ``cpu,cpuacct/`` under it (or the root itself)."""
    root = CGROUP_DIR if cgroup_dir is None else cgroup_dir
    quota = period = ""
    try:
        quota, period = (root / "cpu.max").read_text(encoding="utf-8").split()[:2]
    except (OSError, ValueError):
        for folder in (root, root / "cpu", root / "cpu,cpuacct"):
            try:
                quota = (folder / "cpu.cfs_quota_us").read_text(encoding="utf-8").strip()
                period = (folder / "cpu.cfs_period_us").read_text(encoding="utf-8").strip()
                break
            except OSError:
                continue
        else:
            return None
    try:
        cpus = -(-int(quota) // int(period))
    except (ValueError, ZeroDivisionError):
        return None
    return cpus if cpus >= 1 else None


@dataclass(frozen=True)
class Cpus:
    """What a process was given: the host's cores it may run on, and the container quota if any."""

    host: int
    quota: int | None = None

    @classmethod
    def read(cls, cgroup_dir: Path | None = None) -> Cpus:
        return cls(host=host_cpus(), quota=cgroup_quota(cgroup_dir))

    @property
    def available(self) -> int:
        """The CPUs to size a thread pool by: the host's, or the quota when lower."""
        return self.host if self.quota is None else min(self.host, self.quota)


def available_cpus(cgroup_dir: Path | None = None) -> int:
    """``Cpus.read(cgroup_dir).available``: the CPUs this process may use. ``cgroup_dir`` replaces :data:`CGROUP_DIR`."""
    return Cpus.read(cgroup_dir).available
