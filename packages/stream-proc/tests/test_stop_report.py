"""stop_tree_report says which signals the kernel took: a polite child ends on SIGTERM, one that ignores it gets SIGKILL."""

from __future__ import annotations

import subprocess
import sys
import time
from unittest import mock

from stream_proc import StopReport, stop_tree_report


def test_a_child_that_ends_on_sigterm_reports_term_delivered_and_no_kill() -> None:
    p = subprocess.Popen(["sleep", "30"], start_new_session=True)
    time.sleep(0.1)
    rep = stop_tree_report(p, grace=2.0)
    assert rep == StopReport(survivors=(), term_sent=True, term_delivered=True, kill_sent=False, kill_delivered=False)


def test_a_child_that_ignores_sigterm_is_killed_and_the_report_says_so() -> None:
    code = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('up', flush=True); time.sleep(30)"
    p = subprocess.Popen([sys.executable, "-c", code], start_new_session=True, stdout=subprocess.PIPE)
    assert p.stdout is not None
    p.stdout.readline()
    rep = stop_tree_report(p, grace=0.3)
    assert (rep.survivors, rep.term_delivered, rep.kill_sent, rep.kill_delivered) == ((), True, True, True)


def test_a_child_that_is_already_gone_was_signalled_but_nothing_took_it() -> None:
    p = subprocess.Popen(["true"], start_new_session=True)
    p.wait()
    rep = stop_tree_report(p, grace=0.5)
    assert (rep.survivors, rep.term_sent, rep.term_delivered, rep.kill_delivered, rep.error) == ((), True, False, False, False)


def test_a_stop_that_fails_before_any_signal_says_nothing_was_sent() -> None:
    p = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        with mock.patch("stream_proc.tree.proctable.table", side_effect=RuntimeError("no table")):
            rep = stop_tree_report(p, grace=0.2)
        assert rep == StopReport(survivors=(), term_sent=False, term_delivered=False, kill_sent=False, kill_delivered=False, error=True)
    finally:
        p.kill()
        p.wait()


def test_the_flags_come_from_the_calls_not_from_the_grace() -> None:
    p = subprocess.Popen(["sleep", "30"], start_new_session=True)
    time.sleep(0.1)
    with (
        mock.patch("stream_proc.tree.os.killpg", side_effect=PermissionError),
        mock.patch("stream_proc.tree.os.kill", side_effect=PermissionError),
    ):
        rep = stop_tree_report(p, grace=0.1, prove=0.1)
    try:
        assert (rep.term_sent, rep.term_delivered, rep.kill_sent, rep.kill_delivered) == (True, False, True, False)
        assert rep.survivors == (p.pid,)
    finally:
        p.kill()
        p.wait()
