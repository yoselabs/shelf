"""run(): the supervisor against fake CLIs (shell one-liners that print a recorded stream), no model, no network."""

import json
import os
import signal
import subprocess
import threading
from typing import Any

import pytest

from any_agent import ClaudeHarness, CodexHarness, LaunchSpec, Limits, LogWatcher, NullSink, RunHooks, run
from any_agent import events as ev
from any_agent.procs import Worker
from any_agent.supervisor import StopIntent, Supervisor, end_status

pytestmark = pytest.mark.skipif(os.name == "nt", reason="fake CLIs are shell scripts")


def j(**kw):
    return json.dumps(kw)


CLAUDE_FINAL = j(
    type="assistant",
    message={
        "id": "m2",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 5, "output_tokens": 7},
        "content": [{"type": "text", "text": "the final words"}],
    },
)
CLAUDE_RESULT = j(
    type="result",
    result="claude answer",
    session_id="sess-1",
    is_error=False,
    num_turns=2,
    total_cost_usd=0.25,
    usage={"input_tokens": 15, "output_tokens": 9},
)
CODEX_CMD = j(type="item.started", item={"id": "i2", "type": "command_execution", "command": "cat ~/.ssh/id_rsa", "status": "in_progress"})


def spec(tmp_path, script, stdin=""):
    return LaunchSpec(argv=["sh", "-c", script], env=dict(os.environ), cwd=str(tmp_path), stdin=stdin)


def printing(*lines, then="true"):
    return "".join(f"echo '{ln}'; " for ln in lines) + then


FAST = Limits(first_event_s=30, silence_s=30, grace_s=30)  # nothing here is stopped by the grace unless a test shortens it
SHORT_GRACE = Limits(first_event_s=30, silence_s=30, grace_s=0.4)


def test_a_worker_that_exits_is_summarised_by_its_harness(tmp_path):
    seen: list = []
    hooks = RunHooks(started=seen.append)
    out = run(ClaudeHarness(), spec(tmp_path, printing(CLAUDE_FINAL, CLAUDE_RESULT)), 30, hooks, limits=FAST)
    assert (out.rc, out.timed_out, out.stop, out.watch.why) == (0, False, None, None)
    assert (out.summary.text, out.summary.rc, out.summary.cost) == ("claude answer", 0, 0.25)
    assert out.worker is not None and seen == [out.worker]
    assert hooks.stops == []


def test_the_prompt_goes_in_on_stdin(tmp_path):
    out = run(ClaudeHarness(), spec(tmp_path, "cat", stdin="hello brief\n"), 30, limits=FAST)
    assert out.out == "hello brief\n"


def test_a_worker_that_answers_and_lingers_is_stopped_after_the_grace(tmp_path):
    hooks = RunHooks()
    out = run(ClaudeHarness(), spec(tmp_path, printing(CLAUDE_FINAL, CLAUDE_RESULT, then="sleep 60")), 30, hooks, limits=SHORT_GRACE)
    assert (out.stop, out.timed_out) == ("answer", False)
    assert out.summary.rc == 0 and out.summary.text == "claude answer"
    assert len(hooks.stops) == 1 and hooks.stops[0].term_sent and hooks.stops[0].survivors == []


def test_before_stop_hears_the_intent_and_after_stop_the_report(tmp_path):
    told: list[tuple[Any, ...]] = []
    hooks = RunHooks(before_stop=lambda i: told.append(("before", i)), after_stop=lambda i, r: told.append(("after", i, r)))
    out = run(ClaudeHarness(), spec(tmp_path, printing(CLAUDE_FINAL, CLAUDE_RESULT, then="sleep 60")), 30, hooks, limits=SHORT_GRACE)
    assert out.stop == "answer" and out.worker is not None
    (kind1, intent), (kind2, intent2, rep) = told
    assert (kind1, kind2, intent2) == ("before", "after", intent)
    assert (intent.reason, intent.worker, intent.first_signal, intent.trigger_signal) == ("answer", out.worker, signal.SIGTERM, None)
    assert rep is hooks.stops[0]
    assert (rep.reason, rep.term_sent, rep.term_delivered, rep.kill_sent, rep.kill_delivered) == ("answer", True, True, False, False)


def test_a_refused_intent_stops_nothing_and_propagates_without_a_cleanup_stop(tmp_path):
    def refuse(_intent: StopIntent) -> None:
        msg = "store is busy"
        raise RuntimeError(msg)

    pidfile = tmp_path / "pid"
    hooks = RunHooks(before_stop=refuse)
    with pytest.raises(RuntimeError, match="store is busy"):
        run(ClaudeHarness(), spec(tmp_path, f"echo $$ > {pidfile}; exec sleep 60"), 1, hooks, limits=Limits(first_event_s=60, silence_s=60))
    pid = int(pidfile.read_text())
    try:
        assert hooks.stops == []  # no stop of any name was issued
        os.kill(pid, 0)  # the worker is still up: custody is the caller's
    finally:
        os.kill(pid, signal.SIGKILL)


def test_an_entry_sigterm_is_told_apart_from_the_signal_sent_to_the_agent(tmp_path):
    told: list[StopIntent] = []
    hooks = RunHooks(before_stop=told.append)
    timer = threading.Timer(1.0, lambda: os.kill(os.getpid(), signal.SIGTERM))
    timer.start()
    try:
        with pytest.raises(SystemExit) as info:
            run(ClaudeHarness(), spec(tmp_path, "sleep 60"), 30, hooks, limits=Limits(first_event_s=60, silence_s=60))
    finally:
        timer.cancel()
    assert info.value.code == 128 + signal.SIGTERM
    assert [(i.reason, i.trigger_signal, i.first_signal) for i in told] == [("entry_signal", signal.SIGTERM, signal.SIGTERM)]
    assert [s.reason for s in hooks.stops] == ["entry_signal"]


def test_after_stop_runs_on_an_exceptional_exit_too(tmp_path):
    seen: list[str] = []
    hooks = RunHooks(after_stop=lambda i, r: seen.append(f"{i.reason}:{r.term_delivered}"))
    timer = threading.Timer(1.0, lambda: os.kill(os.getpid(), signal.SIGHUP))
    timer.start()
    try:
        with pytest.raises(SystemExit):
            run(ClaudeHarness(), spec(tmp_path, "sleep 60"), 30, hooks, limits=Limits(first_event_s=60, silence_s=60))
    finally:
        timer.cancel()
    assert seen == ["entry_signal:True"]


def test_a_stop_asked_for_twice_is_made_once(tmp_path):
    told: list[str] = []
    hooks = RunHooks(before_stop=lambda i: told.append(i.reason))
    sup = Supervisor(ClaudeHarness(), hooks, limits=FAST)
    p = subprocess.Popen(["sleep", "60"], start_new_session=True)
    sup.out.worker = Worker(pid=p.pid, pgid=p.pid, start="s", boot="b")
    sup._halt(p, "timeout")
    sup._halt(p, "caller")
    assert (told, [s.reason for s in hooks.stops]) == (["timeout"], ["timeout"])


def test_the_timeout_stops_the_tree(tmp_path):
    hooks = RunHooks()
    out = run(ClaudeHarness(), spec(tmp_path, "sleep 60"), 1, hooks, limits=Limits(first_event_s=60, silence_s=60))
    assert out.timed_out and (out.rc or 0) < 0
    assert len(hooks.stops) == 1
    assert end_status(out.timed_out, None, None, out.rc) == "timeout"


def test_a_silent_worker_is_hung_at_its_first_event_deadline(tmp_path):
    out = run(ClaudeHarness(), spec(tmp_path, "sleep 60"), 30, limits=Limits(first_event_s=1, silence_s=60))
    assert (out.watch.why, out.watch.kind) == ("hung", "first_event")
    assert "printed nothing within 1" in out.watch.words


def test_a_secret_path_in_a_command_stops_the_worker_before_it_goes_on(tmp_path):
    seen: list[ev.HarnessEvent] = []

    def policy(e: ev.HarnessEvent) -> str | None:
        seen.append(e)
        return "~/.ssh/id_rsa" if isinstance(e, ev.Cmd) and ".ssh" in e.text else None

    h = CodexHarness()
    out = run(h, spec(tmp_path, printing(CODEX_CMD, then="sleep 60")), 30, policy=policy, limits=FAST)
    assert out.secret == "~/.ssh/id_rsa"
    assert h.evidence.denials == [
        ev.Denied(tool="Bash", input={"command": "~/.ssh/id_rsa"}, kind="secret", reason="the command names a secret path")
    ]
    assert (out.rc or 0) < 0


def test_a_policy_is_not_asked_of_a_harness_that_blocks_it_itself(tmp_path):
    asked = []
    run(ClaudeHarness(), spec(tmp_path, printing(CLAUDE_RESULT)), 30, policy=asked.append, limits=FAST)  # secret_event is None
    assert asked == []


def test_a_lane_marked_out_stops_the_worker(tmp_path):
    out = run(ClaudeHarness(), spec(tmp_path, "sleep 60"), 30, gone=lambda: ("limit", "usage limit reached"), limits=FAST)
    assert (out.watch.why, out.watch.msg) == ("limit", "usage limit reached")


@pytest.mark.parametrize("why", ["credit", "logged_out"])
def test_a_lane_mark_keeps_its_own_reason(tmp_path, why):
    out = run(ClaudeHarness(), spec(tmp_path, "sleep 60"), 30, gone=lambda: (why, "marked out"), limits=FAST)
    assert (out.watch.why, out.watch.msg) == (why, "marked out")


def test_a_started_hook_that_raises_aborts_before_exec_and_reraises(tmp_path):
    def boom(w: object) -> None:
        raise ZeroDivisionError

    hooks = RunHooks(started=boom)
    with pytest.raises(ZeroDivisionError):
        run(ClaudeHarness(), spec(tmp_path, "sleep 60"), 30, hooks, limits=FAST)
    assert hooks.stops == []  # No harness tree existed to stop: registration failed at the gate.


def test_a_limit_line_in_the_harness_log_stops_the_worker_unless_it_echoes_the_workers_input(tmp_path):
    log = tmp_path / "log"
    log.mkdir()
    watcher = LogWatcher(log, lambda ln: "rate limit" in ln, lambda ln: "pattern=" in ln)
    cmd = (
        f"sleep 1; echo 'service=permission pattern=\"rate limit\"' >> {log}/a.log; "
        f"sleep 1; echo 'ERROR rate limit reached' >> {log}/a.log; sleep 60"
    )
    out = run(ClaudeHarness(), spec(tmp_path, cmd), 30, log=watcher, limits=FAST)
    assert (out.watch.why, out.watch.msg) == ("limit", "ERROR rate limit reached")


def test_a_worker_waiting_for_the_network_is_stopped_once_the_probe_says_it_is_down(tmp_path, monkeypatch):
    monkeypatch.setattr("any_agent.supervisor.NET_GRACE_S", 0.5)
    line = j(type="error", message="Reconnecting... waiting for network")
    out = run(CodexHarness(), spec(tmp_path, printing(line, then="sleep 60")), 30, net_up=lambda: False, limits=FAST)
    assert out.net is True


def test_the_unattended_flag_and_the_null_sink_are_defaults_that_do_nothing(tmp_path):
    out = run(ClaudeHarness(), spec(tmp_path, "true"), 30, live=NullSink(), limits=FAST)
    assert out.rc == 0 and out.stop is None


def test_end_status_names_how_a_run_ended():
    assert end_status(True, None, None, -9) == "timeout"
    assert end_status(False, "hung", None, -9) == "killed"
    assert end_status(False, None, "stall", -9) == "killed"
    assert end_status(False, None, "answer", -9) == "done"
    assert end_status(False, None, None, 0) == "done"
    assert end_status(False, None, None, 1) == "error"
