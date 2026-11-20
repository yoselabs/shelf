"""Churn: a report is rewritten only when a verdict changes; an expiring override is named; one converge batch per run."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import TYPE_CHECKING

import pytest
from blueprint import report
from blueprint.model import REGISTRY, Finding, FixedBy, Verdict, check, failing, passing
from blueprint.runner import EXPIRY_NOTICE_DAYS, Row, run

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from blueprint.testing import Repo


@pytest.fixture
def scratch() -> Iterator[None]:
    before = list(REGISTRY)
    yield
    REGISTRY[:] = before


def _row(id_: str, verdict: Verdict, evidence: str = "e", concern: str = "scratch") -> Row:
    return Row(id_, concern, "s", verdict, None, None, evidence, "fix" if verdict is Verdict.FAILING else "", FixedBy.AGENT)


def test_a_fingerprint_follows_the_verdict_and_not_the_evidence_text() -> None:
    a = _row("scratch.a", Verdict.FAILING, "3 offenders")
    assert report.fingerprint(a) == report.fingerprint(_row("scratch.a", Verdict.FAILING, "4 offenders"))
    assert report.fingerprint(a) != report.fingerprint(_row("scratch.a", Verdict.PASSING))
    assert report.fingerprint(a) != report.fingerprint(_row("scratch.b", Verdict.FAILING))


def _write(repo: Repo, today: date) -> list[Path]:
    return report.write(run(repo.root, concern="scratch", env=repo.env, today=today), repo.root, today, prune=False)


def test_a_rerun_with_the_same_verdicts_does_not_touch_the_report(repo: Repo, scratch: None) -> None:
    state = {"evidence": "one"}

    @check("scratch.red", "red")
    def _red(_ctx: object) -> Finding:
        return failing(state["evidence"], "fix it")

    _write(repo, date(2026, 11, 1))
    path = repo.root / "docs/blueprint/scratch.md"
    first = path.read_text()
    state["evidence"] = "two"  # the same verdict, other words
    _write(repo, date(2026, 11, 2))  # another day
    assert path.read_text() == first


def test_a_changed_verdict_rewrites_only_its_concern(repo: Repo, scratch: None) -> None:
    state = {"ok": False}

    @check("scratch.flip", "flips")
    def _flip(_ctx: object) -> Finding:
        return passing("fine") if state["ok"] else failing("bad", "fix")

    _write(repo, date(2026, 11, 1))
    path = repo.root / "docs/blueprint/scratch.md"
    state["ok"] = True
    _write(repo, date(2026, 11, 2))
    text = path.read_text()
    assert "2026-11-02" in text
    assert "✅" in text


def test_an_override_expiring_soon_is_named_and_one_far_off_is_not(repo: Repo, scratch: None) -> None:
    @check("scratch.red", "red")
    def _red(_ctx: object) -> Finding:
        return failing("red", "fix")

    @check("scratch.blue", "blue")
    def _blue(_ctx: object) -> Finding:
        return failing("blue", "fix")

    repo.write(
        "docs/blueprint/blueprint.toml",
        '[[override]]\nid = "scratch.red"\ncode = "not-applicable"\nreason = "x"\nexpires = 2026-11-30\n'
        '[[override]]\nid = "scratch.blue"\ncode = "not-applicable"\nreason = "x"\nexpires = 2027-06-01\n',
    )
    today = date(2026, 11, 20)
    assert (date(2026, 11, 30) - today).days <= EXPIRY_NOTICE_DAYS
    result = run(repo.root, concern="scratch", env=repo.env, today=today)
    joined = "\n".join(result.notices)
    assert "scratch.red" in joined
    assert "2026-11-30" in joined
    assert "scratch.blue" not in joined
    assert "scratch.red" in report.gate(result)


def test_an_expired_override_is_named_too(repo: Repo, scratch: None) -> None:
    @check("scratch.red", "red")
    def _red(_ctx: object) -> Finding:
        return failing("red", "fix")

    repo.write(
        "docs/blueprint/blueprint.toml",
        '[[override]]\nid = "scratch.red"\ncode = "not-applicable"\nreason = "x"\nexpires = 2026-11-11\n',
    )
    result = run(repo.root, concern="scratch", env=repo.env, today=date(2026, 11, 20))
    assert any("scratch.red" in n and "expired" in n for n in result.notices)


def test_converge_is_one_batch_in_a_stable_order_not_one_per_checkpoint() -> None:
    rows = (
        _row("b.two", Verdict.FAILING, concern="b"),
        _row("a.one", Verdict.FAILING, concern="a"),
        _row("a.ok", Verdict.PASSING, concern="a"),
        replace(_row("a.owner", Verdict.FAILING, concern="a"), fixed_by=FixedBy.OWNER),
    )
    batch = report.converge_batch(rows)
    assert [r.id for r in batch.agent] == ["a.one", "b.two"]
    assert [r.id for r in batch.owner] == ["a.owner"]
    assert batch.commit_message.count("\n") == 0
    assert "a.one" in batch.commit_message
    assert "b.two" in batch.commit_message
