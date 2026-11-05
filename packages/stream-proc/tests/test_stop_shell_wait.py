"""A shell that ``wait``s on a background job must die by signal, never exit 0, when its tree is stopped."""

from __future__ import annotations

import shutil
import subprocess
import time

import pytest
from stream_proc import stop_tree

ROUNDS = 20
SHELLS = [s for s in ("/bin/sh", "/bin/bash") if shutil.which(s)]
SCRIPTS = ["sleep 30 & wait", "sleep 30 & wait; exit 0", "(sleep 30 & wait) & wait"]


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("shell", SHELLS)
def test_a_stopped_shell_waiting_on_a_background_job_is_killed_not_a_success(shell: str, script: str) -> None:
    for _ in range(ROUNDS):
        p = subprocess.Popen([shell, "-c", script], start_new_session=True, stderr=subprocess.DEVNULL)
        time.sleep(0.15)  # the shell is inside `wait`
        assert stop_tree(p, grace=2.0) == ()
        assert p.returncode is not None
        assert p.returncode < 0, f"{shell} -c {script!r} exited {p.returncode} instead of dying by signal"
