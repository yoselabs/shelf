"""The one place a git process is spawned and waited for.

A bounded read runs as the leader of its own process group, and its expiry kills the whole group: Git runs helpers
(``git submodule status`` runs one ``git`` per submodule, a filter or a pager is a child too) and killing only the direct
process would leave a child blocked on the same file, still holding the output pipes. Everything else keeps ``subprocess.run``
semantics: a write killed midway would leave ``index.lock``, so writes are never given a timeout at all.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def run(
    argv: Sequence[str], *, env: Mapping[str, str], timeout: float | None, stdin: bytes | None, group: bool
) -> subprocess.CompletedProcess[bytes]:
    if not group or timeout is None:
        return subprocess.run(argv, check=False, capture_output=True, env=env, timeout=timeout, input=stdin)
    with subprocess.Popen(
        argv,
        stdin=None if stdin is None else subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        start_new_session=True,
    ) as proc:
        try:
            out, err = proc.communicate(stdin, timeout=timeout)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            out, err = proc.communicate()
            raise subprocess.TimeoutExpired(list(argv), timeout, output=out, stderr=err) from None
        return subprocess.CompletedProcess(list(argv), proc.returncode, out, err)
