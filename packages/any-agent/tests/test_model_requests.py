"""Model requests per invocation: one usage record each, counted apart from the turn/completion tracking, tool events never inflate it."""

import json

from any_agent.harnesses.claude import ClaudeHarness
from any_agent.harnesses.codex import CodexHarness
from any_agent.harnesses.opencode import OpenCodeHarness


def feed(h, rows):
    for r in rows:
        h.parse_line(json.dumps(r))


def claude_request(mid, *, tool=False):
    block = {"type": "tool_use", "id": f"t-{mid}", "name": "Read", "input": {"file_path": "x"}} if tool else {"type": "text", "text": "hi"}
    msg = {
        "id": mid,
        "content": [block],
        "usage": {"input_tokens": 10, "output_tokens": 5},
        "stop_reason": "tool_use" if tool else "end_turn",
    }
    return {"type": "assistant", "message": msg}


def test_claude_counts_one_per_model_request_not_per_content_block_or_tool_result():
    h = ClaudeHarness()
    tool_result = {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t-m1", "content": "ok"}]}}
    feed(
        h,
        [
            claude_request("m1", tool=True),
            claude_request("m1", tool=True),
            tool_result,
            claude_request("m2", tool=True),
            claude_request("m3"),
        ],
    )
    assert h.evidence.requests == 3
    assert h.summary(None, "", "", "answer", False).res["requests"] == 3  # no result event: the killed-run summary still carries it


def test_codex_counts_token_count_records_once_each_and_a_single_completion_does_not_add():
    h = CodexHarness()

    def record(total, last):
        usage = {"input_tokens": total, "cached_input_tokens": 0, "output_tokens": 1, "reasoning_output_tokens": 0}
        return {
            "type": "event_msg",
            "payload": {"type": "token_count", "info": {"total_token_usage": usage, "last_token_usage": {**usage, "input_tokens": last}}},
        }

    tool = {
        "type": "item.completed",
        "item": {"id": "c", "type": "command_execution", "command": "ls", "aggregated_output": "", "exit_code": 0, "status": "completed"},
    }
    done = {"type": "turn.completed", "usage": {"input_tokens": 60, "cached_input_tokens": 0, "output_tokens": 3}}
    feed(h, [record(10, 10), tool, record(30, 20), record(30, 20), tool, record(60, 30), done])
    assert (h.evidence.requests, h.evidence.turns) == (3, 1)
    assert h.summary(0, "", "", None, False).res["requests"] == 3


def test_codex_without_per_request_records_reports_one_per_completion():
    h = CodexHarness()
    feed(h, [{"type": "turn.completed", "usage": {"input_tokens": 5, "cached_input_tokens": 0, "output_tokens": 1}}])
    assert (h.evidence.requests, h.summary(0, "", "", None, False).res["requests"]) == (0, 1)


def test_opencode_counts_each_step_finish_with_usage():
    h = OpenCodeHarness()
    step = {
        "type": "step_finish",
        "part": {"reason": "tool-calls", "tokens": {"input": 5, "output": 2, "reasoning": 0, "cache": {"read": 0, "write": 0}}, "cost": 0},
    }
    tool = {"type": "tool_use", "part": {"tool": "bash", "state": {"status": "completed", "input": {"command": "ls"}, "output": ""}}}
    feed(h, [step, tool, step, tool, {**step, "part": {**step["part"], "reason": "stop"}}])
    assert h.evidence.requests == 3
