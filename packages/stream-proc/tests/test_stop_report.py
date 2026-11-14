"""stop_tree_report says which signals the kernel took: a polite child ends on SIGTERM, one that ignores it gets SIGKILL."""

from __future__ import annotations

import subprocess
import sys
import time

from stream_proc import StopReport, stop_tree_report


def test_a_child_that_ends_on_sigterm_reports_term_delivered_and_no_kill() -> None:
    p = subprocess.Popen(["sleep", "30"], start_new_session=True)
    time.sleep(0.1)
    rep = stop_tree_report(p, grace=2.0)
    assert rep == StopReport(survivors=(), term_delivered=True, kill_sent=False, kill_delivered=False)


def test_a_child_that_ignores_sigterm_is_killed_and_the_report_says_so() -> None:
    code = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('up', flush=True); time.sleep(30)"
    p = subprocess.Popen([sys.executable, "-c", code], start_new_session=True, stdout=subprocess.PIPE)
    assert p.stdout is not None
    p.stdout.readline()
    rep = stop_tree_report(p, grace=0.3)
    assert (rep.survivors, rep.term_delivered, rep.kill_sent, rep.kill_delivered) == ((), True, True, True)


def test_a_child_that_is_already_gone_has_no_signal_delivered() -> None:
    p = subprocess.Popen(["true"], start_new_session=True)
    p.wait()
    rep = stop_tree_report(p, grace=0.5)
    assert (rep.survivors, rep.term_delivered, rep.kill_delivered) == ((), False, False)
