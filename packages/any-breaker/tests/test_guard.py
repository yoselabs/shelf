from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from any_breaker import OK, Breaker, BreakerOpenError, Guard, Ledger, Policy

if TYPE_CHECKING:
    from pathlib import Path


class DownError(Exception):
    pass


def make(tmp_path: Path, call, judge, now: list[float]) -> tuple[Guard, Ledger]:
    ledger = Ledger(Breaker(Policy(n=2)), tmp_path / "l.jsonl")
    return Guard(ledger, "svc", call, judge, clock=lambda: now[0]), ledger


async def test_a_raise_counts_and_reraises_then_the_breaker_refuses_the_call(tmp_path: Path) -> None:
    calls: list[int] = []

    async def call() -> str:
        calls.append(1)
        msg = "503"
        raise DownError(msg)

    now = [1000.0]
    guard, ledger = make(tmp_path, call, lambda r, e: "down" if isinstance(e, DownError) else None, now)
    for _ in range(2):
        now[0] += 1
        with pytest.raises(DownError):
            await guard()
    now[0] += 1
    with pytest.raises(BreakerOpenError) as stop:
        await guard()
    assert (len(calls), stop.value.view.rung) == (2, 1)
    assert ledger.state().keys["svc"].recent[0].note == "503"


async def test_a_bad_result_from_code_that_never_raises_is_counted_too(tmp_path: Path) -> None:
    async def call() -> int:
        return 429

    now = [1000.0]
    guard, _ = make(tmp_path, call, lambda r, e: "throttled" if r == 429 else OK, now)
    assert await guard() == 429  # the result still comes back
    now[0] += 1
    assert await guard() == 429
    now[0] += 1
    with pytest.raises(BreakerOpenError):
        await guard()


async def test_an_uncounted_outcome_leaves_no_fact_and_a_success_resets(tmp_path: Path) -> None:
    results = iter([None, "ok", None])

    async def call() -> str | None:
        return next(results)

    now = [1000.0]
    guard, ledger = make(tmp_path, call, lambda r, e: None if r is None else OK, now)
    for _ in range(3):
        now[0] += 1
        await guard()
    assert [k for k, v in ledger.state().keys.items() if v.recent] == []
    assert ledger.state().keys["svc"].last_ok == 1002.0


async def test_the_source_travels_with_the_fact(tmp_path: Path) -> None:
    async def call() -> None:
        raise DownError

    now = [1000.0]
    guard, ledger = make(tmp_path, call, lambda r, e: "down", now)
    for s in ("a", "a"):
        now[0] += 1
        with pytest.raises(DownError):
            await guard(source=s)
    assert [json.loads(line)["source"] for line in ledger.path.read_text(encoding="utf-8").splitlines()] == ["a", "a"]
