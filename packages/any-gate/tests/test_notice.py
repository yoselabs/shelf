"""any_gate.notice: a notice is written only to the descriptor the gate announced, never to a number some other tree reused."""

from __future__ import annotations

import contextlib
import os
import stat
from typing import TYPE_CHECKING

import pytest
from any_gate import notice

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def pipe() -> Iterator[tuple[int, int]]:
    read, write = os.pipe()
    yield read, write
    for fd in (read, write):
        with contextlib.suppress(OSError):
            os.close(fd)


def test_the_announced_descriptor_is_the_one_the_gate_named(pipe: tuple[int, int]) -> None:
    env = notice.announce({}, pipe[1])
    assert notice.descriptor(env) == pipe[1]
    assert env[notice.FD_ENV] == str(pipe[1])  # a shell recipe writes `>&"$GATE_NOTICE_FD"`: the number stays a bare number


def test_a_number_reused_for_another_pipe_is_refused(pipe: tuple[int, int]) -> None:
    env = notice.announce({}, pipe[1])
    other_read, other_write = os.pipe()
    try:
        os.dup2(other_write, pipe[1])  # the number now names a different pipe (an xdist worker's link, say)
        assert os.fstat(pipe[1]).st_ino != int(env[notice.ID_ENV].split(":")[1])
        assert notice.descriptor(env) is None
    finally:
        os.close(other_read)
        os.close(other_write)


def test_a_closed_number_is_refused(pipe: tuple[int, int]) -> None:
    env = notice.announce({}, pipe[1])
    os.close(pipe[1])
    assert notice.descriptor(env) is None


@pytest.mark.parametrize("env", [{}, {"GATE_NOTICE_FD": "2"}, {"GATE_NOTICE_FD": "x", "GATE_NOTICE_ID": "1:2"}, {"GATE_NOTICE_ID": "1:2"}])
def test_a_number_without_a_matching_token_is_refused(env: dict[str, str]) -> None:
    assert notice.descriptor(env) is None


def test_the_token_of_an_ordinary_file_is_not_a_pipe_check(tmp_path: object) -> None:
    fd = os.open(os.devnull, os.O_WRONLY)
    try:
        info = os.fstat(fd)
        assert stat.S_ISCHR(info.st_mode)
        assert notice.descriptor(notice.announce({}, fd)) == fd
    finally:
        os.close(fd)


def test_scrub_drops_both_variables_and_nothing_else() -> None:
    env = {"GATE_NOTICE_FD": "5", "GATE_NOTICE_ID": "1:2", "PATH": "/bin"}
    assert notice.scrub(env) == {"PATH": "/bin"}
