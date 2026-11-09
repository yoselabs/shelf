"""Native identity observations preserve uncertainty, boot changes and PID reuse."""

from __future__ import annotations

import ctypes
import errno
import os
import select
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from stream_proc import OwnedProcess, inspect_process, observe_owned, owned, popen_registered, procfs, procmac

if TYPE_CHECKING:
    from stream_proc.procfs import Proc


def test_current_process_and_wrong_retained_identity() -> None:
    observation = inspect_process(os.getpid())
    identity = observation.identity
    assert observation.kind == "matching" and identity is not None
    assert observe_owned(identity).kind == "matching"
    assert observe_owned(replace(identity, start=identity.start + "0")).kind == "different_process"
    assert observe_owned(replace(identity, boot="another boot")).kind == "different_process"


def test_unknown_boot_never_becomes_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(owned, "boot_id", lambda: None)
    assert inspect_process(os.getpid()).kind == "unknown"
    assert observe_owned(OwnedProcess(os.getpid(), os.getpgrp(), "1", "boot")).kind == "unknown"


def test_boot_change_during_observation_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    boots = iter(["before", "after"])
    monkeypatch.setattr(owned, "boot_id", lambda: next(boots))
    assert inspect_process(os.getpid()).kind == "unknown"


@pytest.mark.skipif(sys.platform != "linux", reason="Linux native /proc path")
@pytest.mark.parametrize("failure", [PermissionError(errno.EACCES, "denied"), OSError(errno.EIO, "unreadable")])
def test_unreadable_native_process_is_unknown(monkeypatch: pytest.MonkeyPatch, failure: OSError) -> None:
    original = Path.read_text

    def read(path: Path, *, encoding: str | None = None, errors: str | None = None) -> str:
        if path.name == "stat":
            raise failure
        return original(path, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", read)
    assert inspect_process(os.getpid()).kind == "unknown"


@pytest.mark.parametrize("content", ["", "12 (broken)", "invalid encoding fields"])
def test_malformed_native_record_is_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str) -> None:
    (tmp_path / "12").mkdir()
    (tmp_path / "12" / "stat").write_text(content)
    monkeypatch.setattr(procfs, "PROC", tmp_path)
    assert procfs.inspect(12) == "unknown"
    assert procfs.inspect(13) == "gone"


@pytest.mark.parametrize("native", [procfs, procmac])
def test_zombie_is_known_gone(monkeypatch: pytest.MonkeyPatch, native: object) -> None:
    row = procfs.Proc(12, 1, 12, 12, "100", "Z")

    def inspect(_pid: int) -> Proc:
        return row

    monkeypatch.setattr(native, "inspect", inspect)
    monkeypatch.setattr(owned.sys, "platform", "darwin" if native is procmac else "linux")
    monkeypatch.setattr(owned, "boot_id", lambda: "boot")
    assert inspect_process(12).kind == "gone"


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires actual macOS native APIs")
def test_native_macos_boot_uuid_and_identity() -> None:
    assert owned.boot_id() is not None
    assert inspect_process(os.getpid()).kind == "matching"


@pytest.mark.parametrize("error, expected", [(errno.ESRCH, "gone"), (errno.EPERM, "unknown"), (0, "unknown")])
def test_macos_native_errno_preserves_unknown(monkeypatch: pytest.MonkeyPatch, error: int, expected: str) -> None:
    def unavailable(*_args: object) -> int:
        ctypes.set_errno(error)
        return 0

    monkeypatch.setattr(procmac, "_lib", lambda: SimpleNamespace(proc_pidinfo=unavailable))
    assert procmac.inspect(12) == expected


def test_process_group_change_preserves_the_registered_process() -> None:
    identities: list[OwnedProcess] = []
    code = "import os,sys\nsys.stdin.readline()\nos.setsid()\nprint('group changed',flush=True)\nsys.stdin.readline()\n"
    child, original = popen_registered([sys.executable, "-I", "-S", "-c", code], registered=identities.append, start_new_session=False)
    try:
        assert child.stdin is not None and child.stdout is not None
        assert original.pgid == os.getpgrp() and original.pgid != child.pid
        child.stdin.write(b"change group\n")
        child.stdin.flush()
        assert select.select([child.stdout], [], [], 5)[0]
        assert child.stdout.readline() == b"group changed\n"
        observation = observe_owned(original)
        assert observation.kind == "matching"
        current = observation.identity
        assert current is not None
        assert (current.pid, current.start, current.boot) == (original.pid, original.start, original.boot)
        assert current.pgid == child.pid and current.pgid != original.pgid
        assert identities == [original]
        child.communicate(b"finish\n", timeout=5)
        assert child.returncode == 0
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)
