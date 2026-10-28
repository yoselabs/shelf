"""The macOS libproc path: struct layouts on every OS, the libproc calls on darwin only."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time

import pytest
from stream_proc import procmac

darwin = pytest.mark.skipif(sys.platform != "darwin", reason="libproc is macOS only")
PY = sys.executable

BSDINFO_OFFSETS = {
    "pbi_flags": 0,
    "pbi_status": 4,
    "pbi_xstatus": 8,
    "pbi_pid": 12,
    "pbi_ppid": 16,
    "pbi_uid": 20,
    "pbi_gid": 24,
    "pbi_ruid": 28,
    "pbi_rgid": 32,
    "pbi_svuid": 36,
    "pbi_svgid": 40,
    "rfu_1": 44,
    "pbi_comm": 48,
    "pbi_name": 64,
    "pbi_nfiles": 96,
    "pbi_pgid": 100,
    "pbi_pjobc": 104,
    "e_tdev": 108,
    "e_tpgid": 112,
    "pbi_nice": 116,
    "pbi_start_tvsec": 120,
    "pbi_start_tvusec": 128,
}
TASKINFO_OFFSETS = {
    "pti_virtual_size": 0,
    "pti_resident_size": 8,
    "pti_total_user": 16,
    "pti_total_system": 24,
    "pti_threads_user": 32,
    "pti_threads_system": 40,
    "pti_policy": 48,
    "pti_faults": 52,
    "pti_pageins": 56,
    "pti_cow_faults": 60,
    "pti_messages_sent": 64,
    "pti_messages_received": 68,
    "pti_syscalls_mach": 72,
    "pti_syscalls_unix": 76,
    "pti_csw": 80,
    "pti_threadnum": 84,
    "pti_numrunning": 88,
    "pti_priority": 92,
}


def offsets(struct: type[ctypes.Structure]) -> dict[str, int]:
    return {name: getattr(struct, name).offset for name, *_ in struct._fields_}


def test_proc_bsdinfo_layout_matches_sys_proc_info_h() -> None:
    assert ctypes.sizeof(procmac.ProcBsdInfo) == 136
    assert offsets(procmac.ProcBsdInfo) == BSDINFO_OFFSETS


def test_proc_taskinfo_layout_matches_sys_proc_info_h() -> None:
    assert ctypes.sizeof(procmac.ProcTaskInfo) == 96
    assert offsets(procmac.ProcTaskInfo) == TASKINFO_OFFSETS


def test_timebase_layout() -> None:
    assert ctypes.sizeof(procmac.TimebaseInfo) == 8


@pytest.mark.skipif(sys.platform == "darwin", reason="off macOS the dylib must stay untouched")
def test_off_macos_the_dylib_is_never_loaded() -> None:
    assert procmac._lib() is None
    assert not procmac.has_table()
    assert procmac.table() == {}
    assert procmac.proc_start(os.getpid()) is None
    assert procmac.alive(os.getpid())  # signal 0 fallback


def spawn(code: str) -> subprocess.Popen[str]:
    return subprocess.Popen([PY, "-c", code], stdout=subprocess.PIPE, text=True)


@darwin
def test_self_row() -> None:
    row = procmac.read(os.getpid())
    assert row is not None
    assert (row.pid, row.ppid, row.pgid) == (os.getpid(), os.getppid(), os.getpgrp())
    assert row.state == "R"
    assert row.cmd
    assert row.start
    assert procmac.table()[os.getpid()].start == row.start


@darwin
def test_a_spawned_child_and_its_grandchild_are_listed() -> None:
    p = spawn(
        "import subprocess, sys, time\n"
        f"g = subprocess.Popen([{PY!r}, '-c', 'import time; time.sleep(30)'])\n"
        "print(g.pid, flush=True)\ntime.sleep(30)\n"
    )
    try:
        assert p.stdout is not None
        gpid = int(p.stdout.readline())
        assert p.pid in procmac.child_pids(os.getpid())
        assert [r.pid for r in procmac.descendants(os.getpid())].count(gpid) == 1
        assert gpid in {r.pid for r in procmac.descendants(p.pid)}
        assert gpid in {r.pid for r in procmac.descendants(os.getpid())}
        assert procmac.alive(gpid)
    finally:
        p.kill()
        p.wait()


@darwin
def test_cpu_time_is_monotone() -> None:
    first = procmac.read(os.getpid())
    assert first is not None
    end = time.monotonic() + 0.3
    while time.monotonic() < end:
        sum(range(10000))
    second = procmac.read(os.getpid())
    assert second is not None
    assert second.cpu_s >= first.cpu_s > 0
    assert second.cpu_s > first.cpu_s


@darwin
def test_start_token_is_stable_and_differs_per_process() -> None:
    p = spawn("import time; time.sleep(30)")
    try:
        mine = procmac.proc_start(os.getpid())
        assert mine
        assert procmac.proc_start(os.getpid()) == mine
        theirs = procmac.proc_start(p.pid)
        assert theirs
        assert theirs != mine
        assert procmac.alive(p.pid, theirs)
        assert not procmac.alive(p.pid, theirs + "0")
    finally:
        p.kill()
        p.wait()
    assert procmac.proc_start(p.pid) is None
    assert not procmac.alive(p.pid)


@darwin
def test_a_zombie_is_not_alive() -> None:
    p = subprocess.Popen([PY, "-c", "pass"])
    deadline = time.monotonic() + 10
    while procmac.proc_start(p.pid) is not None and time.monotonic() < deadline:
        time.sleep(0.05)  # exited, not yet reaped: a zombie
    try:
        assert procmac.proc_start(p.pid) is None
        assert not procmac.alive(p.pid)
    finally:
        p.wait()
