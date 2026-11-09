"""One supervised execution keeps answer validity separate from execution facts."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from any_agent import (
    CodexHarness,
    DecodedAnswer,
    InvalidAnswer,
    LaunchSpec,
    MissingAnswer,
    RunHooks,
    RunOutcome,
    Summary,
    classify,
    decode_answer,
    run,
)
from any_agent.procs import Worker
from any_agent.testing import FakeRun

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class Plan:
    text: str


def decode_plan(value: object) -> Plan:
    if isinstance(value, dict) and len(value) == 1:
        text = value.get("plan")
        if isinstance(text, str):
            return Plan(text)
    msg = "expected exactly one string plan"
    raise ValueError(msg)


@pytest.mark.parametrize("text", ['{"plan":"next"}', ' \n {"plan":"next"} \t'])
def test_typed_answer_is_decoded_once(text: str) -> None:
    seen: list[object] = []

    def decode(value: object) -> Plan:
        seen.append(value)
        return decode_plan(value)

    assert decode_answer(text, decode) == DecodedAnswer(Plan("next"))
    assert seen == [{"plan": "next"}]


@pytest.mark.parametrize("text", ["", " \n\t"])
def test_missing_answer_never_calls_decoder(text: str) -> None:
    assert decode_answer(text, decode_plan) == MissingAnswer()


@pytest.mark.parametrize(
    "text",
    [
        "no json",
        '{"plan":',
        '{"plan":"a"} {"plan":"b"}',
        '```json\n{"plan":"a"}\n```',
        '{"plan":"a"} trailing',
        '{"plan":"a","plan":"b"}',
        '{"nested":{"x":1,"x":2}}',
        '{"plan":NaN}',
        '{"plan":Infinity}',
        '{"plan":-Infinity}',
        '{"plan":1e999}',
    ],
)
def test_ambiguous_or_non_json_answer_is_not_repaired(text: str) -> None:
    answer = decode_answer(text, decode_plan)
    assert isinstance(answer, InvalidAnswer)
    assert answer.kind == "json"
    assert 0 < len(answer.reason) <= 300


@pytest.mark.parametrize("text", ['{"plan":4}', '{"other":"a"}', '["a"]', "null"])
def test_valid_json_still_needs_domain_validation(text: str) -> None:
    answer = decode_answer(text, decode_plan)
    assert isinstance(answer, InvalidAnswer)
    assert answer.kind == "schema"


def test_json_null_is_not_missing_and_schema_error_is_bounded() -> None:
    assert decode_answer("null", lambda value: value) == DecodedAnswer(None)

    def reject(_value: object) -> None:
        raise ValueError("x" * 600)

    answer = decode_answer("{}", reject)
    assert isinstance(answer, InvalidAnswer)
    assert answer.kind == "schema"
    assert len(answer.reason) == 300


@pytest.mark.parametrize("failure", [TypeError, RuntimeError, RecursionError, KeyboardInterrupt])
def test_decoder_programming_fault_is_not_invalid_model_output(failure: type[BaseException]) -> None:
    def broken(_value: object) -> Plan:
        msg = "decoder fault"
        raise failure(msg)

    with pytest.raises(failure, match="decoder fault"):
        decode_answer("{}", broken)


def spec_for(tmp_path: Path, answer: str, rc: int, refs: tuple[str, ...]) -> LaunchSpec:
    events: list[dict[str, object]] = [
        {"type": "item.completed", "item": {"type": "agent_message", "text": answer}},
        {"type": "turn.completed", "usage": {"input_tokens": 7, "output_tokens": 3}},
        *({"type": "thread.started", "thread_id": ref} for ref in refs),
    ]
    code = "; ".join(f"print({json.dumps(event)!r}, flush=True)" for event in events)
    code += f"; raise SystemExit({rc})"
    return LaunchSpec(argv=[sys.executable, "-I", "-S", "-c", code], env={}, cwd=str(tmp_path), stdin="prompt")


def fake_outcome(answer: str, rc: int, refs: tuple[str, ...]) -> RunOutcome:
    return RunOutcome(
        rc=rc,
        worker=Worker(pid=401, pgid=401, start="fixture-start", boot="fixture-boot"),
        summary=Summary(
            text=answer,
            rc=rc,
            stands=True,
            res={"ref": refs[-1] if refs else None, "tokens": {"in": 7, "cached": None, "out": 3}},
        ),
    )


@pytest.mark.parametrize("implementation", ["native", "fake"])
@pytest.mark.parametrize(
    "answer, rc, refs",
    [
        ('{"plan":"next"}', 0, ()),
        ('{"plan":"next"}', 0, ("late-session",)),
        ('{"plan":"next"}', 7, ("session",)),
        ('{"plan":3}', 0, ()),
        ("not json", 0, ()),
        ("", 0, ()),
    ],
)
def test_same_consumer_decodes_one_execution(
    tmp_path: Path,
    implementation: str,
    answer: str,
    rc: int,
    refs: tuple[str, ...],
) -> None:
    harness = CodexHarness()
    spec = spec_for(tmp_path, answer, rc, refs)
    fake = FakeRun(fake_outcome(answer, rc, refs), refs=refs)
    observed: list[str] = []
    workers: list[Worker] = []

    def registered(worker: Worker) -> None:
        workers.append(worker)
        observed.append("registered")

    def session(ref: str) -> None:
        assert workers
        observed.append(ref)

    hooks = RunHooks(started=registered, ref=session, unattended=False)
    execute = run if implementation == "native" else fake
    raw = execute(harness, spec, 10, hooks)
    observed.append("returned")
    decoded = decode_answer(raw.summary.text, decode_plan)
    assert observed == ["registered", *refs, "returned"]
    assert raw.worker == workers[0]
    assert raw.rc == rc
    assert raw.summary.res["ref"] == (refs[-1] if refs else None)
    assert raw.summary.res["tokens"] == {"in": 7, "cached": None, "out": 3}
    assert raw.summary.data is None
    assert raw.summary.cost == 0  # Existing default, not a measurement of free execution.
    assert decoded == decode_answer(answer, decode_plan)
    if rc:
        assert isinstance(decoded, DecodedAnswer)
        failure = classify(raw.rc, raw.summary.vendor, raw.summary.stderr, raw.timed_out, raw.summary.work)
        assert failure is not None
    if implementation == "fake":
        assert fake.calls == [(harness, spec, 10, hooks)]


@pytest.mark.parametrize("implementation", ["native", "fake"])
@pytest.mark.parametrize("failure", [ValueError, KeyboardInterrupt])
def test_registration_refusal_has_no_ref_or_terminal_answer(
    tmp_path: Path,
    implementation: str,
    failure: type[BaseException],
) -> None:
    marker = tmp_path / "executed"
    spec = LaunchSpec(
        argv=[sys.executable, "-c", f"open({str(marker)!r},'w').write('executed')"],
        env={},
        cwd=str(tmp_path),
        stdin="",
    )
    fake = FakeRun(fake_outcome('{"plan":"next"}', 0, ("ref",)), refs=("ref",))
    refs: list[str] = []

    def refuse(_worker: Worker) -> None:
        msg = "registration refused"
        raise failure(msg)

    execute = run if implementation == "native" else fake
    with pytest.raises(failure, match="registration refused"):
        execute(CodexHarness(), spec, 10, RunHooks(started=refuse, ref=refs.append))
    assert not marker.exists()
    assert refs == []


def test_fake_is_consumed_once_and_preserves_answer_grace_facts(tmp_path: Path) -> None:
    raw = fake_outcome('{"plan":"next"}', -15, ("ref",))
    raw.stop = "answer"
    raw.summary.stands = True
    fake = FakeRun(raw, refs=("ref", "ref"))
    spec = spec_for(tmp_path, "unused", 0, ())
    refs: list[str] = []
    result = fake(CodexHarness(), spec, 10, RunHooks(ref=refs.append))
    assert result is raw
    assert result.rc == -15 and result.stop == "answer" and result.summary.stands
    assert decode_answer(result.summary.text, decode_plan) == DecodedAnswer(Plan("next"))
    assert refs == ["ref", "ref"]
    with pytest.raises(RuntimeError, match="consumed"):
        fake(CodexHarness(), spec, 10)
    assert len(fake.calls) == 1


def test_fake_requires_explicit_worker() -> None:
    with pytest.raises(ValueError, match="worker"):
        FakeRun(RunOutcome())


def test_excessive_json_depth_is_invalid_output_not_decoder_fault() -> None:
    text = "[" * 10_000
    answer = decode_answer(text, decode_plan)
    assert isinstance(answer, InvalidAnswer)
    assert answer.kind == "json"
    assert 0 < len(answer.reason) <= 300


@pytest.mark.parametrize("terminal_ref", ["other-session", None])
def test_fake_refuses_inconsistent_reported_session(terminal_ref: str | None) -> None:
    raw = fake_outcome("{}", 0, ())
    raw.summary.res["ref"] = terminal_ref
    with pytest.raises(ValueError, match="ref"):
        FakeRun(raw, refs=("observed-session",))


@pytest.mark.parametrize("reported", [False, True])
def test_fake_accepts_matching_or_unspecified_terminal_ref(tmp_path: Path, *, reported: bool) -> None:
    raw = fake_outcome("{}", 0, ("observed-session",))
    if not reported:
        del raw.summary.res["ref"]
    fake = FakeRun(raw, refs=("older-session", "observed-session"))
    refs: list[str] = []
    assert fake(CodexHarness(), spec_for(tmp_path, "unused", 0, ()), 10, RunHooks(ref=refs.append)) is raw
    assert refs == ["older-session", "observed-session"]
