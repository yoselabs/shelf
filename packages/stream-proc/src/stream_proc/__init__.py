"""stream-proc — run a child, stream its lines, stop its whole tree and prove it dead.

- :func:`run` — one child in a session of its own; stdout/stderr lines to callbacks, wall and idle
  timeouts, a stop flag; a typed :class:`Result`.
- :func:`stop_tree` — SIGTERM, grace, SIGKILL, a sweep of descendants that left the group, a proof;
  :func:`stop_tree_report` — the same, with a :class:`StopReport` of the signals the kernel took.
- :func:`alive`, :func:`proc_start` — pid-reuse-safe liveness (``/proc`` on Linux, libproc on macOS);
  :func:`table`, :func:`descendants` — the process table (pid, ppid, pgid, uid, rss bytes, start token);
  :func:`group_alive` — is any process in a group; :func:`group_rss` — resident bytes of a group.
- :func:`capture` — :func:`run` to the end, output as text, exit 124 on a timeout, optional heartbeat ``tick``.
- :func:`capture_bytes` — the same, output as exact bytes, optional ``input`` on stdin, stdin devnull or inherited,
  and :func:`run_inherited` for a child that writes to our stdout/stderr.
- :func:`stop_pid`, :class:`PidHandle` — stop a process we did not spawn, only while its start token matches.
- :class:`TermHold`, :func:`popen_held` — a SIGTERM landing during a spawn still stops the child.
- :class:`Pump` — the readers, stdin feeder and pipe lifetime of a held ``Popen`` (what :func:`run` and :func:`capture_bytes` use).
- :func:`popen_registered` — the command executes only after a callback durably registered its identity;
  :func:`run_registered` — that gate plus :func:`run`'s supervision, stdin /dev/null, stderr merged into one log.

Stdlib only (``ctypes`` on macOS), POSIX.
"""

from stream_proc.capture import Captured, CapturedBytes, capture, capture_bytes, run_inherited
from stream_proc.hold import TermHold, popen_held
from stream_proc.owned import IdentityUnavailableError, OwnedProcess, ProcessObservation, inspect_process, observe_owned
from stream_proc.pid import PidHandle, stop_pid
from stream_proc.procfs import Proc
from stream_proc.proctable import alive, descendants, group_alive, group_rss, proc_start, table
from stream_proc.pump import Pump
from stream_proc.registered import RegisteredStartUncertainError, popen_registered
from stream_proc.runner import Kind, Result, run, run_registered
from stream_proc.tree import StopReport, stop_tree, stop_tree_report

__all__ = [
    "Captured",
    "CapturedBytes",
    "IdentityUnavailableError",
    "Kind",
    "OwnedProcess",
    "PidHandle",
    "Proc",
    "ProcessObservation",
    "Pump",
    "RegisteredStartUncertainError",
    "Result",
    "StopReport",
    "TermHold",
    "alive",
    "capture",
    "capture_bytes",
    "descendants",
    "group_alive",
    "group_rss",
    "inspect_process",
    "observe_owned",
    "popen_held",
    "popen_registered",
    "proc_start",
    "run",
    "run_inherited",
    "run_registered",
    "stop_pid",
    "stop_tree",
    "stop_tree_report",
    "table",
]
