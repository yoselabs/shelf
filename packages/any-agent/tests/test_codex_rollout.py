"""The Codex rollout file: one token_count record per model request, the usage a killed run would otherwise lose."""

import json
from datetime import UTC, datetime
from pathlib import Path

from any_agent.harnesses import codex_rollout
from any_agent.harnesses.codex import CodexHarness

REF = "01a1891e-1155-77b1-af0a-f0d2b004bf08"


def count(at: str, total: int | None, *, ordinal: int = 0) -> dict:
    info = None
    if total is not None:
        usage = {"input_tokens": total, "cached_input_tokens": total // 2, "output_tokens": total // 10, "reasoning_output_tokens": 0}
        info = {"total_token_usage": usage, "last_token_usage": usage}
    return {"timestamp": at, "ordinal": ordinal, "type": "event_msg", "payload": {"type": "token_count", "info": info}}


def rollout(tmp_path: Path, rows: list[dict]) -> Path:
    folder = tmp_path / "sessions" / "2026" / "11" / "14"
    folder.mkdir(parents=True)
    (folder / f"rollout-2026-11-14T10-00-00-{REF}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return tmp_path / "sessions"


def test_three_requests_are_three_and_a_repeated_total_or_an_empty_info_is_not_a_request(tmp_path):
    rows = [
        count("2026-11-14T10:00:01.000Z", 100),
        count("2026-11-14T10:00:02.000Z", 100),  # the same running total again
        count("2026-11-14T10:00:03.000Z", None),  # a rate-limit update
        {"timestamp": "2026-11-14T10:00:04.000Z", "type": "response_item", "payload": {"type": "function_call"}},  # a tool event
        count("2026-11-14T10:00:05.000Z", 250),
        count("2026-11-14T10:00:06.000Z", 400),
    ]
    used = codex_rollout.read(rollout(tmp_path, rows), REF)
    assert used is not None and used.requests == 3
    assert used.tokens() == {"in": 400, "cached": 200, "out": 40, "reasoning": 0}


def test_a_resumed_thread_counts_only_the_requests_since_the_run_began(tmp_path):
    rows = [count("2026-11-14T10:00:01.000Z", 100), count("2026-11-14T10:00:02.000Z", 200), count("2026-11-14T11:00:01.000Z", 300)]
    since = datetime(2026, 11, 14, 10, 30, tzinfo=UTC).timestamp()
    used = codex_rollout.read(rollout(tmp_path, rows), REF, since)
    assert used is not None and (used.requests, used.before["input_tokens"], used.total["input_tokens"]) == (1, 200, 300)


def test_no_rollout_is_none_not_an_error(tmp_path):
    assert codex_rollout.read(tmp_path, REF) is None


def test_a_killed_codex_run_reports_the_rollouts_requests_and_tokens_and_says_the_usage_is_incomplete(tmp_path):
    h = CodexHarness(env={})
    h.sessions = rollout(tmp_path, [count("2026-11-14T10:00:01.000Z", 100), count("2026-11-14T10:00:02.000Z", 300)])
    h.parse_line(json.dumps({"type": "thread.started", "thread_id": REF}))
    res = h.summary(-15, "", "", None, True).res  # no turn.completed ever came
    assert (res["requests"], res["tokens"], res["usage_incomplete"], res["turns"]) == (
        2,
        {"in": 300, "cached": 150, "out": 30, "reasoning": 0},
        True,
        None,
    )


def test_a_finished_codex_run_keeps_the_stream_tokens_and_is_complete(tmp_path):
    h = CodexHarness(env={})
    h.sessions = rollout(
        tmp_path, [count("2026-11-14T10:00:01.000Z", 100), count("2026-11-14T10:00:02.000Z", 300), count("2026-11-14T10:00:03.000Z", 500)]
    )
    h.parse_line(json.dumps({"type": "thread.started", "thread_id": REF}))
    h.parse_line(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 500, "cached_input_tokens": 250, "output_tokens": 9}}))
    res = h.summary(0, "", "", None, False).res
    assert (res["requests"], res["tokens"], res["usage_incomplete"]) == (3, {"in": 500, "cached": 250, "out": 9}, False)


def test_reasoning_tokens_come_from_the_stream_turn_and_the_rollout_and_are_absent_when_unreported(tmp_path):
    h = CodexHarness(env={})
    h.parse_line(
        json.dumps(
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 9, "cached_input_tokens": 1, "output_tokens": 5, "reasoning_output_tokens": 3},
            }
        )
    )
    assert h.evidence.tokens == {"in": 9, "cached": 1, "out": 5, "reasoning": 3}
    quiet = CodexHarness(env={})
    quiet.parse_line(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 9, "output_tokens": 5}}))
    assert quiet.evidence.tokens == {"in": 9, "cached": None, "out": 5}
    usage = {"input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 8, "reasoning_output_tokens": 6}
    rows = [
        {
            "timestamp": "2026-11-14T10:00:01.000Z",
            "type": "event_msg",
            "payload": {"type": "token_count", "info": {"total_token_usage": usage, "last_token_usage": usage}},
        }
    ]
    used = codex_rollout.read(rollout(tmp_path, rows), REF)
    assert used is not None and used.tokens() == {"in": 10, "cached": 0, "out": 8, "reasoning": 6}
