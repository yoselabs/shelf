from __future__ import annotations

from typing import TYPE_CHECKING

from any_breaker import Breaker, Fact, Ledger, Policy

if TYPE_CHECKING:
    from pathlib import Path


def three(path: Path) -> Ledger:
    ledger = Ledger(Breaker(Policy()), path)
    for i in range(3):
        ledger.record(Fact("x", 1000 + i, "k", note="boom"))
    return ledger


def test_recorded_facts_open_the_breaker_and_a_second_ledger_replays_the_file(tmp_path: Path) -> None:
    ledger = three(tmp_path / "sub" / "ledger.jsonl")
    assert not ledger.allow("k", 1010).usable
    assert ledger.allow("k", 1010 + 900).canary
    again = Ledger(Breaker(Policy()), ledger.path)
    assert again.allow("k", 1010) == ledger.allow("k", 1010)


def test_a_missing_file_allows_everything(tmp_path: Path) -> None:
    assert Ledger(Breaker(), tmp_path / "none.jsonl").allow("k", 1).usable


def test_the_state_is_folded_incrementally_and_sees_new_facts(tmp_path: Path) -> None:
    ledger = Ledger(Breaker(Policy(n=2)), tmp_path / "l.jsonl")
    ledger.record(Fact("x", 1000, "k"))
    assert ledger.allow("k", 1001).usable
    ledger.record(Fact("x", 1002, "k"))
    assert not ledger.allow("k", 1003).usable


def test_garbage_and_half_written_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    ledger = three(path)
    with path.open("ab") as fh:
        fh.write(b'not json\n{"kind": 1}\n{"kind":"x","ts":2000')  # no newline: still being written
    assert not ledger.allow("k", 1010).usable
    with path.open("ab") as fh:
        fh.write(b',"key":"z"}\n')
    assert ledger.state().keys["z"].recent[0].ts == 2000


def test_a_truncated_file_is_refolded_from_the_start(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    ledger = three(path)
    assert not ledger.allow("k", 1010).usable
    path.write_text("", encoding="utf-8")
    assert ledger.allow("k", 1010).usable


def test_a_fact_older_than_the_folded_state_is_ignored_like_a_checkpoint(tmp_path: Path) -> None:
    ledger = three(tmp_path / "l.jsonl")
    ledger.allow("k", 1010)
    ledger.record(Fact("ok", 500, "k"))  # late arrival, before the state's ts
    assert not ledger.allow("k", 1010).usable
