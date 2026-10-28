"""Every exit path of ``run`` closes the child's pipes: no ResourceWarning for an unclosed pipe or file."""

from __future__ import annotations

import gc
import sys
import threading
import warnings
from typing import TYPE_CHECKING, override

import pytest
from stream_proc import run

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

from stream_proc import Result

PY = sys.executable
LOUD = "import sys, time\nprint('up', flush=True)\nprint('err', file=sys.stderr, flush=True)\n"


@pytest.fixture
def leaks() -> Iterator[list[warnings.WarningMessage]]:
    """The ResourceWarnings raised while the test ran (a warning in ``__del__`` cannot be raised, so it is recorded)."""
    gc.collect()
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always", ResourceWarning)
        yield seen
        gc.collect()


def _clean(leaks: list[warnings.WarningMessage], go: Callable[[], Result]) -> None:
    go()
    gc.collect()
    assert [str(w.message) for w in leaks if issubclass(w.category, ResourceWarning)] == []


def test_normal_exit_closes_the_pipes(leaks: list[warnings.WarningMessage]) -> None:
    _clean(leaks, lambda: run([PY, "-c", LOUD], on_stdout=lambda _l: None))


def test_wall_timeout_closes_the_pipes(leaks: list[warnings.WarningMessage]) -> None:
    _clean(leaks, lambda: run([PY, "-c", LOUD + "time.sleep(60)"], timeout=0.5, grace=1))


def test_idle_timeout_closes_the_pipes(leaks: list[warnings.WarningMessage]) -> None:
    _clean(leaks, lambda: run([PY, "-c", LOUD + "time.sleep(60)"], idle=0.5, grace=1))


def test_stop_flag_closes_the_pipes(leaks: list[warnings.WarningMessage]) -> None:
    flag = threading.Event()
    _clean(leaks, lambda: run([PY, "-c", LOUD + "time.sleep(60)"], on_stdout=lambda _l: flag.set(), stop=flag, grace=1))


def test_an_interrupt_closes_the_pipes(leaks: list[warnings.WarningMessage]) -> None:
    class Stop(threading.Event):
        @override
        def is_set(self) -> bool:
            raise KeyboardInterrupt

    def go() -> Result:
        with pytest.raises(KeyboardInterrupt):
            run([PY, "-c", LOUD + "time.sleep(60)"], stop=Stop(), grace=1)
        return Result(0, None, None, 0, 0, None, 0.0)

    _clean(leaks, go)


def test_a_held_pipe_does_not_keep_the_reader_or_the_pipe(leaks: list[warnings.WarningMessage]) -> None:
    """A grandchild that outlives the child and keeps the pipe open: run still returns, readers end, pipes close."""
    code = (
        "import subprocess, sys\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(3)'], start_new_session=True)\n"
        "print('x', flush=True)\n"
    )
    before = threading.active_count()
    _clean(leaks, lambda: run([PY, "-c", code], drain=0.3))
    assert threading.active_count() <= before
