"""Real harmless children exercise registration, interruption and bootstrap isolation."""

from __future__ import annotations

import errno
import json
import os
import select
import signal
import struct
import subprocess
import sys
from pathlib import Path

import pytest
from stream_proc import (
    IdentityUnavailableError,
    OwnedProcess,
    ProcessObservation,
    RegisteredStartUncertainError,
    inspect_process,
    observe_owned,
    popen_registered,
    registered,
)


def test_identity_and_stdio_survive_exec(tmp_path: Path) -> None:
    identities: list[OwnedProcess] = []
    code = (
        "import os,sys,json; "
        "print(json.dumps([os.getpid(),os.getpgrp(),os.getcwd(),sys.argv[1:],sys.stdin.read()])); "
        "print('diagnostic', file=sys.stderr); "
        "fds=[]\n"
        "for fd in map(int,os.listdir('/dev/fd')):\n"
        " if fd <= 2: continue\n"
        " try: os.fstat(fd)\n"
        " except OSError: pass\n"
        " else: fds.append(fd)\n"
        "print(json.dumps(fds))"
    )
    p, identity = popen_registered(
        [sys.executable, "-I", "-S", "-c", code, "a b", "λ", "$(touch forbidden);*"], cwd=tmp_path, registered=identities.append
    )
    out, err = p.communicate(b"prompt\n", timeout=5)
    values, fds = out.splitlines()
    assert json.loads(values) == [p.pid, p.pid, str(tmp_path), ["a b", "λ", "$(touch forbidden);*"], "prompt\n"]
    assert json.loads(fds) == []
    assert err == b"diagnostic\n" and p.returncode == 0
    assert identities == [identity]
    assert identity.pid == identity.pgid == p.pid and identity.start and identity.boot
    assert observe_owned(identity).kind == "gone"


def test_original_target_environment_and_hostile_python_startup(tmp_path: Path) -> None:
    marker = tmp_path / "startup"
    (tmp_path / "sitecustomize.py").write_text(f"open({str(marker)!r},'w').write('bad')")
    (tmp_path / "json.py").write_text(f"open({str(marker)!r},'w').write('bad')")
    env = {"PATH": "/usr/bin:/bin", "LC_CTYPE": "C", "PYTHONPATH": str(tmp_path), "EXACT": "λ=value"}

    def register(identity: OwnedProcess) -> None:
        assert inspect_process(identity.pid).identity == identity
        assert not marker.exists()

    p, _ = popen_registered(["/usr/bin/env"], env=env, cwd=tmp_path, registered=register)
    out, err = p.communicate(timeout=5)
    assert dict(line.split("=", 1) for line in out.decode().splitlines()) == env
    assert err == b"" and p.returncode == 0
    assert not marker.exists()


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt, SystemExit])
def test_registration_failure_never_runs_target(tmp_path: Path, failure: type[BaseException]) -> None:
    marker = tmp_path / "target"
    identities: list[OwnedProcess] = []

    def reject(identity: OwnedProcess) -> None:
        identities.append(identity)
        raise failure

    with pytest.raises(failure):
        popen_registered([sys.executable, "-c", f"open({str(marker)!r},'w').write('bad')"], registered=reject)
    assert not marker.exists()
    assert observe_owned(identities[0]).kind == "gone"


def test_unknown_identity_refuses_registration_and_exec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    marker = tmp_path / "target"
    calls: list[OwnedProcess] = []
    monkeypatch.setattr(registered, "inspect_process", lambda _pid: ProcessObservation("unknown"))
    with pytest.raises(IdentityUnavailableError):
        popen_registered([sys.executable, "-c", f"open({str(marker)!r},'w').write('bad')"], registered=calls.append)
    assert calls == [] and not marker.exists()


def test_missing_target_is_an_explicit_startup_error() -> None:
    identities: list[OwnedProcess] = []
    with pytest.raises(FileNotFoundError) as failure:
        popen_registered(["/not/a/program"], registered=identities.append)
    assert failure.value.filename == "/not/a/program"
    assert len(identities) == 1
    assert observe_owned(identities[0]).kind == "gone"


@pytest.mark.parametrize("mode", ["empty", "header", "partial", "invalid", "oversize", "timeout"])
def test_bootstrap_rejects_incomplete_or_invalid_permit(tmp_path: Path, mode: str) -> None:
    marker = tmp_path / "target"
    target = f"open({str(marker)!r},'w').write('bad')"
    raw = json.dumps({"permit": "exec", "argv": [sys.executable, "-c", target], "env": dict(os.environ)}).encode()
    data = {
        "empty": b"",
        "header": b"\0\0",
        "partial": struct.pack("!I", len(raw) + 1) + raw,
        "invalid": struct.pack("!I", 2) + b"{}",
        "oversize": struct.pack("!I", 9 * 1024 * 1024),
        "timeout": b"",
    }[mode]
    control_read, control_write = os.pipe()
    status_read, status_write = os.pipe()
    script = Path(registered.__file__).with_name("_exec_gate.py")
    p = subprocess.Popen(
        [sys.executable, "-I", "-S", str(script), str(control_read), str(status_write), "0.1"],
        pass_fds=(control_read, status_write),
        cwd=tmp_path,
    )
    os.close(control_read)
    os.close(status_write)
    try:
        os.write(control_write, data)
        if mode != "timeout":
            os.close(control_write)
            control_write = -1
        assert p.wait(timeout=5) == 127
        error = errno.ETIMEDOUT if mode == "timeout" else errno.EPROTO
        assert os.read(status_read, 5) == b"R" + struct.pack("!I", error)
        assert not marker.exists()
    finally:
        if control_write >= 0:
            os.close(control_write)
        os.close(status_read)
        if p.poll() is None:
            p.kill()
            p.wait(timeout=5)


def test_controller_death_before_permission_never_executes(tmp_path: Path) -> None:
    marker = tmp_path / "target"
    target = f"open({str(marker)!r}, 'w').write('bad')"
    code = (
        "import json,sys; from stream_proc import popen_registered\n"
        "def register(identity):\n"
        " print(identity.pid,flush=True)\n"
        " sys.stdin.buffer.read(1)\n"
        f"popen_registered([sys.executable,'-c',{target!r}], registered=register)\n"
    )
    controller = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert controller.stdout is not None
        assert select.select([controller.stdout], [], [], 5)[0]
        assert int(controller.stdout.readline()) > 1
        controller.kill()
        controller.communicate(timeout=5)
        assert not marker.exists()
    finally:
        if controller.poll() is None:
            controller.kill()
            controller.communicate(timeout=5)


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_held_signal_replay_aborts_gated_child(tmp_path: Path, signum: int) -> None:
    marker = tmp_path / "target"
    target = f"open({str(marker)!r},'w').write('bad')"
    code = (
        "import signal,sys; from stream_proc import TermHold,popen_registered\n"
        "original=TermHold.__enter__\n"
        "def enter(self):\n"
        " result=original(self)\n"
        f" signal.raise_signal({signum})\n"
        " return result\n"
        "def stop(*_): raise KeyboardInterrupt\n"
        f"signal.signal({signum},stop)\n"
        "TermHold.__enter__=enter\n"
        "try:\n"
        f" popen_registered([sys.executable,'-c',{target!r}],registered=lambda identity: None)\n"
        "except KeyboardInterrupt: print('interrupted')\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=5, check=False)
    assert result.returncode == 0 and result.stdout == b"interrupted\n"
    assert not marker.exists()


def test_failure_after_permission_retains_identity_and_reports_uncertainty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    marker = tmp_path / "executed"
    fifo = tmp_path / "notify"
    os.mkfifo(fifo)
    reader = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
    target = f"open({str(marker)!r},'w').write('executed'); import os; f=os.open({str(fifo)!r},os.O_WRONLY); os.write(f,b'x'); os.close(f)"
    identities: list[OwnedProcess] = []

    def lost_status(_fd: int, _deadline: float) -> int | None:
        assert select.select([reader], [], [], 5)[0]
        raise KeyboardInterrupt

    monkeypatch.setattr(registered, "_exec_status", lost_status)
    try:
        with pytest.raises(RegisteredStartUncertainError) as failure:
            popen_registered([sys.executable, "-c", target], registered=identities.append)
        assert marker.read_text() == "executed"
        assert failure.value.identity == identities[0]
        assert failure.value.leader_reaped
        assert isinstance(failure.value.__cause__, KeyboardInterrupt)
    finally:
        os.close(reader)


def test_controller_death_after_permission_keeps_prior_registration(tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    target = f"open({str(marker)!r},'w').write('executed'); print('executed',flush=True); input()"
    code = (
        "import sys; from stream_proc import popen_registered\n"
        "def register(identity): print('registered',identity.pid,identity.boot,flush=True)\n"
        f"p,identity=popen_registered([sys.executable,'-c',{target!r}],registered=register)\n"
        "print(p.stdout.readline().decode().strip(),flush=True)\n"
        "sys.stdin.buffer.read(1)\n"
    )
    controller = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert controller.stdout is not None
        assert select.select([controller.stdout], [], [], 5)[0]
        registration = controller.stdout.readline().decode().split()
        assert registration[0] == "registered" and int(registration[1]) > 1 and registration[2]
        assert select.select([controller.stdout], [], [], 5)[0]
        assert controller.stdout.readline() == b"executed\n"
        controller.kill()
        controller.communicate(timeout=5)
        assert marker.read_text() == "executed"
    finally:
        if controller.poll() is None:
            controller.kill()
            controller.communicate(timeout=5)
