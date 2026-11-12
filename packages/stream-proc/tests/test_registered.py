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
import threading
from pathlib import Path

import pytest
from stream_proc import (
    IdentityUnavailableError,
    OwnedProcess,
    ProcessObservation,
    RegisteredStartUncertainError,
    group_alive,
    inspect_process,
    observe_owned,
    popen_registered,
    proc_start,
    registered,
    run_registered,
    stop_pid,
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


@pytest.mark.parametrize("flag, expected", [("--help", 0), ("--unknown-gate-option", 2)])
def test_exec_gate_cli_help_and_unknown_flag_are_safe(tmp_path: Path, flag: str, expected: int) -> None:
    script = Path(registered.__file__).with_name("_exec_gate.py")
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(script), flag],
        cwd=tmp_path,
        input=b"unrelated prompt stdin",
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == expected
    assert b"usage:" in (result.stdout + result.stderr).lower()
    assert b"Traceback" not in result.stderr
    if flag == "--help":
        assert b"registration" in result.stdout.lower() and result.stderr == b""
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "values", [["3", "4", "1", "--unknown-gate-option"], ["0", "4", "1"], ["3", "3", "1"], ["3", "4", "nan"], ["3", "4", "-1"]]
)
def test_exec_gate_invalid_arguments_do_not_touch_protocol_descriptors(tmp_path: Path, values: list[str]) -> None:
    script = Path(registered.__file__).with_name("_exec_gate.py")
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(script), *values],
        cwd=tmp_path,
        input=b"unrelated prompt stdin",
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 2 and result.stdout == b""
    assert b"usage:" in result.stderr.lower() and b"Traceback" not in result.stderr
    if "--unknown-gate-option" in values:
        assert b"--unknown-gate-option" in result.stderr
    assert not list(tmp_path.iterdir())


def test_run_registered_registers_before_the_command_and_logs_one_merged_stream(tmp_path: Path) -> None:
    marker = tmp_path / "ran"
    events: list[object] = []

    def register(identity: OwnedProcess) -> None:
        assert observe_owned(identity).kind == "matching" and not marker.exists()
        events.append(identity)

    script = f"touch {marker}; echo out; echo err >&2; cat; echo after"
    result = run_registered(["/bin/sh", "-c", script], registered=register, cwd=tmp_path, timeout=5, on_line=events.append)
    identity = events[0]
    assert isinstance(identity, OwnedProcess)
    assert events[1:] == [b"out\n", b"err\n", b"after\n"]
    assert (result.returncode, result.signal, result.timed_out, result.exec_errno) == (0, None, None, None)
    assert result.pid == result.pgid == identity.pid == identity.pgid and result.start == identity.start
    assert observe_owned(identity).kind == "gone" and not group_alive(result.pgid)


def test_run_registered_reports_a_nonzero_exit_with_its_partial_log() -> None:
    lines: list[bytes] = []
    result = run_registered(["/bin/sh", "-c", "echo partial; printf torn; exit 3"], registered=lambda _: None, on_line=lines.append)
    assert (result.returncode, result.timed_out, result.exec_errno) == (3, None, None)
    assert lines == [b"partial\n", b"torn"]


@pytest.mark.parametrize("ending", ["wall", "stopped"])
def test_run_registered_stops_and_proves_the_whole_tree_on_deadline_or_stop(ending: str) -> None:
    stop = threading.Event()
    lines: list[bytes] = []

    def line(raw: bytes) -> None:
        lines.append(raw)
        if ending == "stopped":
            stop.set()

    result = run_registered(
        ["/bin/sh", "-c", "sleep 30 & echo started; wait"],
        registered=lambda _: None,
        on_line=line,
        timeout=0.5 if ending == "wall" else 30,
        stop=stop,
        grace=0.5,
    )
    assert result.timed_out == ending and result.returncode is None and result.signal is not None
    assert result.survivors == () and not group_alive(result.pgid)
    assert lines == [b"started\n"]


@pytest.mark.parametrize(("make", "number"), [(False, errno.ENOENT), (True, errno.EACCES)])
def test_run_registered_exec_failure_after_registration_is_a_result(tmp_path: Path, *, make: bool, number: int) -> None:
    program = tmp_path / "program"
    if make:
        program.write_text("#!/bin/sh\necho never\n")
        program.chmod(0o600)
    identities: list[OwnedProcess] = []
    lines: list[bytes] = []
    result = run_registered([str(program)], registered=identities.append, on_line=lines.append)
    assert result.exec_errno == number and result.returncode is None and result.timed_out is None
    assert [result.pid, result.pgid] == [identities[0].pid, identities[0].pgid] and lines == []
    assert observe_owned(identities[0]).kind == "gone"


def test_run_registered_leaves_a_descendant_in_the_group_to_the_caller() -> None:
    lines: list[bytes] = []
    result = run_registered(["/bin/sh", "-c", "sleep 30 >/dev/null 2>&1 & echo $!"], registered=lambda _: None, on_line=lines.append)
    sleeper = int(lines[0])
    try:
        assert result.returncode == 0 and result.timed_out is None
        assert group_alive(result.pgid) and os.getpgid(sleeper) == result.pgid
    finally:
        assert stop_pid(sleeper, proc_start(sleeper), grace=0.5) == ()
    assert not group_alive(result.pgid)


def test_run_registered_never_runs_the_command_when_registration_fails(tmp_path: Path) -> None:
    marker = tmp_path / "ran"

    def reject(_identity: OwnedProcess) -> None:
        raise OSError(errno.EIO, "store unavailable")

    with pytest.raises(OSError, match="store unavailable"):
        run_registered(["/bin/sh", "-c", f"touch {marker}"], registered=reject)
    assert not marker.exists()


def test_run_registered_propagates_an_uncertain_start_with_the_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    identities: list[OwnedProcess] = []

    def lost_status(_fd: int, _deadline: float) -> int | None:
        raise RuntimeError

    monkeypatch.setattr(registered, "_exec_status", lost_status)
    with pytest.raises(RegisteredStartUncertainError) as failure:
        run_registered(["/bin/true"], registered=identities.append)
    assert failure.value.identity == identities[0]


def test_run_registered_caps_a_newline_less_line() -> None:
    got: list[bytes] = []
    res = run_registered(
        [sys.executable, "-c", "import sys; sys.stdout.write('q' * 5000)"],
        registered=lambda _identity: None,
        on_line=got.append,
        max_line=2048,
    )
    assert res.returncode == 0
    assert [len(piece) for piece in got] == [2048, 2048, 904]
    assert res.split_lines == 2
