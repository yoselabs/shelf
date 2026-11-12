"""Activity: recorded Codex and Claude Code streams folded into display records with durations and waits, and the line codec."""

from pathlib import Path

from any_agent import events as ev
from any_agent.activity import Activity, Timeline, decode, encode
from any_agent.harnesses.claude import ClaudeHarness
from any_agent.harnesses.codex import CodexHarness

GOLDEN = Path(__file__).resolve().parent / "golden"


def replay(harness, name, step=2.0):
    """Every line of a golden stream arrives `step` seconds after the previous one."""
    timeline, found, now = Timeline(), [], 100.0
    for line in (GOLDEN / name).read_text().splitlines():
        now += step
        for event in harness.parse_line(line):
            found += timeline.add(event, now)
    return found


class TestCodex:
    def test_a_command_is_written_running_then_finished_with_its_duration_and_the_wait_before_it(self):
        found = [a for a in replay(CodexHarness(), "codex_session.jsonl") if a.kind == "command"]
        assert [(a.state, a.text, a.id) for a in found] == [("running", "ls", "c1"), ("finished", "ls", "c1")]
        running, finished = found
        assert running.waited_ms is None
        assert finished.at == running.at
        assert finished.duration_ms == 4000  # the item.updated line sits between its start and its completion
        assert finished.exit_code == 0

    def test_a_message_follows_the_end_of_the_previous_action(self):
        found = replay(CodexHarness(), "codex_session.jsonl")
        message = next(a for a in found if a.kind == "message")
        assert message.text == "done" and message.state == "finished" and message.waited_ms is not None

    def test_reasoning_tokens_and_unknown_lines_make_no_activity(self):
        texts = [a.text for a in replay(CodexHarness(), "codex_session.jsonl")]
        assert "plan the change" not in texts and "secret" not in " ".join(texts)

    def test_a_retry_and_a_failure_are_waiting_and_error(self):
        kinds = {a.kind for a in replay(CodexHarness(), "codex_reconnecting.jsonl")}
        assert "waiting" in kinds
        assert {a.kind for a in replay(CodexHarness(), "codex_bad_request.jsonl")} >= {"error"}


class TestClaude:
    def test_bash_is_a_command_and_other_tools_are_tools_and_an_error_result_has_an_exit_code(self):
        found = replay(ClaudeHarness(), "claude_session.jsonl")
        commands = [a for a in found if a.kind == "command" and a.state == "finished"]
        assert [(a.text, a.exit_code) for a in commands] == [("ls", None), ("git push", 1)]
        tool = next(a for a in found if a.kind == "tool" and a.state == "finished")
        assert (tool.name, tool.text) == ("Edit", "x.py")
        assert [a.text for a in found if a.kind == "message"] == ["let me look", "all done"]


class TestTimeline:
    def test_a_harness_measured_duration_wins_over_ours(self):
        timeline = Timeline()
        timeline.add(ev.Cmd(id="a", text="make"), 10.0)
        (done,) = timeline.add(ev.CmdEnd(id="a", text="make", exit=2, secs=1.5), 30.0)
        assert (done.duration_ms, done.exit_code, done.at) == (1500, 2, 10.0)

    def test_a_finish_without_a_start_is_still_one_record(self):
        (done,) = Timeline().add(ev.CmdEnd(id="a", text="make", exit=0), 30.0)
        assert (done.at, done.duration_ms) == (30.0, None)

    def test_a_shell_wrapper_is_not_shown(self):
        wrapped = ("/run/bin/bash -lc 'ls -la'", "sh -c \"echo 'a b'\"", "bash -lc", "ls -la")
        assert [Timeline().add(ev.Cmd(id="a", text=t), 1.0)[0].text for t in wrapped] == ["ls -la", "echo 'a b'", "bash -lc", "ls -la"]

    def test_text_is_cut_to_its_cap(self):
        (found,) = Timeline().add(ev.Msg(text="x" * 5000), 1.0)
        assert len(found.text) == 2000 and found.text.endswith("…")


class TestCodec:
    def test_a_record_round_trips(self):
        a = Activity(kind="tool", state="finished", at=12.5, text="x.py", id="t", name="Edit", waited_ms=7, duration_ms=9, exit_code=0)
        assert decode(encode(a)) == a

    def test_anything_else_decodes_to_none(self):
        for line in (
            "",
            "[truncated]",
            "{",
            "[]",
            '{"k":"command"}',
            '{"k":"nope","s":"running","at":1,"t":""}',
            '{"k":"message","s":"finished","at":true,"t":""}',
        ):
            assert decode(line) is None
