"""judge: first block wins, three rule answer shapes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from any_shell_policy import Verdict, judge, parse

if TYPE_CHECKING:
    from collections.abc import Mapping


def no_kill_by_name(tool: str, args: Mapping[str, Any]) -> str:
    cmds = parse(str(args.get("command") or "")) if tool == "Bash" else []
    if any(c.name in {"pkill", "killall"} for c in cmds or []):
        return "kill the PID you started"
    return ""


def test_allowed_when_no_rule_blocks() -> None:
    assert judge([], "Bash", {}) == Verdict()
    assert judge([no_kill_by_name], "Bash", {"command": "ls"}) == Verdict()


def test_string_rule_blocks_with_its_reason() -> None:
    assert judge([no_kill_by_name], "Bash", {"command": "sudo pkill x"}) == Verdict(True, "kill the PID you started")


def test_other_tools_are_untouched() -> None:
    assert not judge([no_kill_by_name], "Read", {"command": "pkill x"}).blocked


def test_first_block_wins_and_later_rules_do_not_run() -> None:
    calls: list[str] = []

    def first(tool: str, args: Mapping[str, Any]) -> Verdict:
        calls.append("first")
        return Verdict(True, "first")

    def second(tool: str, args: Mapping[str, Any]) -> str:
        calls.append("second")
        return "second"

    assert judge([lambda t, a: None, first, second], "Bash", {}) == Verdict(True, "first")
    assert calls == ["first"]


def test_verdict_and_none_answers_allow() -> None:
    assert judge([lambda t, a: Verdict(), lambda t, a: None, lambda t, a: ""], "Bash", {}) == Verdict()
