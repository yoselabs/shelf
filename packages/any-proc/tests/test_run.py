"""Running a real child once: arguments in, limits on, one marked result out."""

from __future__ import annotations

import io
import json
import os
import sys
from typing import TYPE_CHECKING

import pytest
from any_proc.run import (
    DEFAULT_MAX_ARGS_BYTES,
    RESULT_MARKER,
    ArgsError,
    Limits,
    call,
    emit,
    encode_args,
    parse_result,
    read_args,
    user_task_count,
)

if TYPE_CHECKING:
    from pathlib import Path

# A child that echoes its arguments back through the package's own child side.
_ECHO = "from any_proc.run import emit, read_args\nemit({'got': read_args()})\n"


def _py(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def test_arguments_reach_the_child_over_stdin_and_the_result_comes_back() -> None:
    out = call(_py(_ECHO), args={"path": "raw/x.pdf"}, timeout=30)
    assert out.result == {"got": {"path": "raw/x.pdf"}}
    assert out.returncode == 0
    assert not out.timed_out


def test_no_arguments_reads_as_none() -> None:
    assert call(_py(_ECHO), timeout=30).result == {"got": None}


def test_no_arguments_never_reads_the_parents_stdin() -> None:
    # The parent's fd 0 is a terminal that stays open: a child reading it would wait for
    # the timeout instead of seeing no arguments.
    read_end, write_end = os.pipe()
    saved = os.dup(0)
    os.dup2(read_end, 0)
    try:
        out = call(_py(_ECHO), timeout=10)
    finally:
        os.dup2(saved, 0)
        for fd in (saved, read_end, write_end):
            os.close(fd)
    assert not out.timed_out
    assert out.result == {"got": None}


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(["not", "a", "dict"], id="non_object"),
        pytest.param({"blob": "x" * (DEFAULT_MAX_ARGS_BYTES + 10)}, id="oversized"),
        pytest.param({"v": object()}, id="unserializable"),
    ],
)
def test_bad_arguments_are_refused_before_spawning(tmp_path: Path, args: object) -> None:
    sentinel = tmp_path / "RAN"
    with pytest.raises(ArgsError):
        call(_py(f"open({str(sentinel)!r}, 'w').write('x')"), args=args, timeout=30)  # type: ignore[arg-type]
    assert not sentinel.exists()


def test_the_cap_is_configurable_and_inclusive() -> None:
    assert encode_args({"k": "x"}, max_bytes=10) == '{"k": "x"}'
    with pytest.raises(ArgsError):
        encode_args({"k": "x" * 20}, max_bytes=10)


def test_a_child_that_writes_no_result_reports_its_code_and_stderr() -> None:
    out = call(_py("import sys; sys.stderr.write('boom'); sys.exit(3)"), timeout=30)
    assert out.result is None
    assert out.returncode == 3
    assert out.stderr == "boom"


def test_a_timeout_kills_the_child_and_says_so() -> None:
    out = call(_py("import time; time.sleep(30)"), timeout=0.5)
    assert out.timed_out
    assert out.returncode is None
    assert out.result is None
    assert out.duration_ms < 10_000


def test_the_child_observes_its_limits() -> None:
    code = (
        "import resource\nfrom any_proc.run import emit\n"
        "emit({'fsize': resource.getrlimit(resource.RLIMIT_FSIZE)[0], 'nproc': resource.getrlimit(resource.RLIMIT_NPROC)[0]})\n"
    )
    out = call(_py(code), timeout=30, limits=Limits(file_size_bytes=100 * 1024 * 1024, process_headroom=64))
    assert out.result is not None
    assert out.result["fsize"] == 100 * 1024 * 1024
    running = user_task_count()
    assert running is not None
    assert out.result["nproc"] > 64  # headroom over what the user already runs, not a total of 64


def test_a_child_writing_past_its_file_size_cap_fails_and_the_parent_survives(tmp_path: Path) -> None:
    target = tmp_path / "big.bin"
    code = f"open({str(target)!r}, 'wb').write(b'x' * 8388608)\nfrom any_proc.run import emit\nemit({{'reached': True}})\n"
    out = call(_py(code), timeout=30, limits=Limits(file_size_bytes=1024 * 1024))
    assert out.result is None
    assert out.returncode != 0
    assert call(_py(_ECHO), timeout=30).result == {"got": None}


def test_parse_takes_the_last_marked_line() -> None:
    stdout = f'log\n{RESULT_MARKER} {{"n": 1}}\nmore\n{RESULT_MARKER} {{"n": 2}}\n'
    assert parse_result(stdout) == {"n": 2}


@pytest.mark.parametrize("stdout", ["", "no marker\n", f"{RESULT_MARKER} not json\n", f"{RESULT_MARKER} [1, 2]\n"])
def test_parse_without_a_marked_object_is_none(stdout: str) -> None:
    assert parse_result(stdout) is None


def test_emit_and_parse_agree() -> None:
    buf = io.StringIO()
    emit({"status": "success", "result": [1, "ü"]}, buf)
    assert parse_result(buf.getvalue()) == {"status": "success", "result": [1, "ü"]}


@pytest.mark.parametrize(("text", "expected"), [("", None), ("  \n", None), ('{"a": 1}', {"a": 1})])
def test_read_args(text: str, expected: object) -> None:
    assert read_args(io.StringIO(text)) == expected


@pytest.mark.parametrize("text", ["[1]", "not json"])
def test_read_args_refuses_anything_but_an_object(text: str) -> None:
    with pytest.raises(ArgsError):
        read_args(io.StringIO(text))


def test_read_args_on_a_closed_stdin_is_none() -> None:
    closed = io.StringIO("{}")
    closed.close()
    assert read_args(closed) is None


def test_env_and_cwd_reach_the_child(tmp_path: Path) -> None:
    code = "import os\nfrom any_proc.run import emit\nemit({'v': os.environ.get('ANY_PROC_T'), 'cwd': os.getcwd()})\n"
    env = {"ANY_PROC_T": "yes", "PATH": "/usr/bin:/bin", "PYTHONPATH": ":".join(sys.path)}
    out = call(_py(code), env=env, cwd=tmp_path, timeout=30)
    assert out.result is not None
    assert out.result["v"] == "yes"
    assert json.dumps(out.result["cwd"]).endswith(f'{tmp_path.name}"')
