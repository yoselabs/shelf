"""``group_alive``: is any process in a process group, from ``killpg(pgid, 0)`` alone."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from stream_proc import group_alive

if TYPE_CHECKING:
    from collections.abc import Callable


def test_a_live_group_is_alive_and_a_reaped_one_is_not() -> None:
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
    try:
        assert group_alive(p.pid)
    finally:
        p.kill()
        p.wait()
    assert not group_alive(p.pid)


def test_our_own_group_is_alive() -> None:
    assert group_alive(os.getpgrp())


@pytest.mark.parametrize("pgid", [0, 1, -1, -500])
def test_group_ids_that_must_never_be_probed_say_false(pgid: int) -> None:
    assert not group_alive(pgid)


def _raising(exc: BaseException) -> Callable[[int, int], None]:
    def killpg(pgid: int, sig: int) -> None:
        raise exc

    return killpg


def test_a_group_we_may_not_signal_still_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "killpg", _raising(PermissionError(1, "denied")))
    assert group_alive(4242)


def test_a_vanished_group_is_dead(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "killpg", _raising(ProcessLookupError(3, "gone")))
    assert not group_alive(4242)
