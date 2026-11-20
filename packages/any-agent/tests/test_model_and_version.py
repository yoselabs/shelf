"""Every harness reports, in the run's result, the model that actually answered and the CLI's own version ("" when it cannot tell)."""

import json
from pathlib import Path

from any_agent.harnesses.claude import ClaudeHarness
from any_agent.harnesses.codex import CodexHarness
from any_agent.harnesses.opencode import OpenCodeHarness

GOLDEN = Path(__file__).parent / "golden"
REF = "01a1891e-1155-77b1-af0a-f0d2b004bf08"


def feed(h, name: str) -> None:
    for line in (GOLDEN / name).read_text().splitlines():
        h.parse_line(line)


def test_claude_reports_the_resolved_model_and_cli_version_from_the_init_event():
    h = ClaudeHarness(env={})
    feed(h, "claude_init_session.jsonl")
    res = h.summary(0, "", "", None, False).res
    assert (res["model_resolved"], res["harness_version"]) == ("claude-opus-4-7-20261015", "2.1.143")


def test_claude_killed_after_init_still_reports_both():
    h = ClaudeHarness(env={})
    h.parse_line((GOLDEN / "claude_init_session.jsonl").read_text().splitlines()[0])
    res = h.summary(-15, "", "", None, True).res
    assert (res["model_resolved"], res["harness_version"]) == ("claude-opus-4-7-20261015", "2.1.143")


def test_claude_without_init_takes_the_model_of_the_first_reply_and_leaves_the_version_empty():
    h = ClaudeHarness(env={})
    feed(h, "claude_session.jsonl")  # the older recording: no init model
    res = h.summary(0, "", "", None, False).res
    assert (res["model_resolved"], res["harness_version"]) == ("", "")
    h.parse_line(json.dumps({"type": "assistant", "message": {"id": "m9", "model": "<synthetic>", "content": []}}))
    h.parse_line(json.dumps({"type": "assistant", "message": {"id": "m10", "model": "claude-sonnet-5-5", "content": []}}))
    assert h.summary(0, "", "", None, False).res["model_resolved"] == "claude-sonnet-5-5"


def codex_with_rollout(tmp_path: Path, name: str | None) -> CodexHarness:
    h = CodexHarness(env={})
    folder = tmp_path / "sessions" / "2026" / "11" / "14"
    folder.mkdir(parents=True)
    if name:
        (folder / f"rollout-2026-11-14T10-00-00-{REF}.jsonl").write_text((GOLDEN / name).read_text())
    h.sessions = tmp_path / "sessions"
    h.parse_line(json.dumps({"type": "thread.started", "thread_id": REF}))
    return h


def test_codex_reports_the_model_and_cli_version_from_the_rollout(tmp_path):
    res = codex_with_rollout(tmp_path, "rollout_codex_meta.jsonl").summary(0, "", "", None, False).res
    assert (res["model_resolved"], res["harness_version"]) == ("gpt-5.5-2026-10-01", "0.131.0")


def test_codex_without_a_rollout_says_empty(tmp_path):
    res = codex_with_rollout(tmp_path, None).summary(0, "", "", None, False).res
    assert (res["model_resolved"], res["harness_version"]) == ("", "")


def test_codex_that_never_started_says_empty():
    res = CodexHarness(env={}).summary(1, "", "", None, False).res
    assert (res["model_resolved"], res["harness_version"]) == ("", "")


def test_opencode_says_empty_because_its_json_stream_names_neither():
    h = OpenCodeHarness(env={})
    feed(h, "opencode_session.jsonl")
    res = h.summary(0, "", "", None, False).res
    assert (res["model_resolved"], res["harness_version"]) == ("", "")
