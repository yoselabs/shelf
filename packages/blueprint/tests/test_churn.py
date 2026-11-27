"""Churn: a report is rewritten only when a verdict changes; an expiring override is named; one converge batch per run."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import TYPE_CHECKING

import pytest
from blueprint import report
from blueprint.model import REGISTRY, Context, Finding, FixedBy, Verdict, check, failing, passing
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
    return report.write_concern(run(repo.root, concern="scratch", env=repo.env, today=today), repo.root, today)


def test_a_rerun_with_the_same_verdicts_does_not_touch_the_report(repo: Repo, scratch: None) -> None:
    state = {"evidence": "one"}

    @check("scratch.red", "red")
    def _red(_ctx: object) -> Finding:
        return failing(state["evidence"], "fix it")

    _write(repo, date(2026, 11, 1))
    path = repo.root / ".blueprint/reports/scratch.md"
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
    path = repo.root / ".blueprint/reports/scratch.md"
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


def _override(repo: Repo, check_id: str, expires: str = "2027-06-01") -> None:
    repo.write(
        "docs/blueprint/blueprint.toml",
        f'[[override]]\nid = "{check_id}"\ncode = "not-applicable"\nreason = "x"\nexpires = {expires}\n',
    )


def test_an_override_whose_checkpoint_passes_without_it_is_named_as_dead(repo: Repo, scratch: None) -> None:
    @check("scratch.fine", "passes on its own")
    def _fine(_ctx: object) -> Finding:
        return passing("fine")

    _override(repo, "scratch.fine")
    result = run(repo.root, concern="scratch", env=repo.env, today=date(2026, 11, 20))
    assert any("scratch.fine" in n and "passes without it" in n for n in result.notices)
    assert "scratch.fine" in report.gate(result)


def test_an_override_that_is_still_needed_is_not_named_dead(repo: Repo, scratch: None) -> None:
    @check("scratch.red", "red")
    def _red(_ctx: object) -> Finding:
        return failing("red", "fix")

    _override(repo, "scratch.red")
    result = run(repo.root, concern="scratch", env=repo.env, today=date(2026, 11, 20))
    assert not any("passes without it" in n for n in result.notices)


def test_an_override_for_a_checkpoint_that_did_not_run_is_not_judged(repo: Repo, scratch: None) -> None:
    @check("scratch.slow", "audit only", audit_only=True)
    def _slow(_ctx: object) -> Finding:
        return passing("fine")

    _override(repo, "scratch.slow")
    result = run(repo.root, concern="scratch", env=repo.env, today=date(2026, 11, 20))
    assert not any("passes without it" in n for n in result.notices)


def _scoped(repo: Repo, check_id: str, scope: str) -> None:
    repo.write(
        "docs/blueprint/blueprint.toml",
        f'[[override]]\nid = "{check_id}"\nscope = "{scope}"\nreason = "x"\nexpires = 2027-06-01\n',
    )


def _dead_notices(repo: Repo) -> list[str]:
    result = run(repo.root, concern="scratch", env=repo.env, today=date(2026, 11, 20))
    return [n for n in result.notices if "excuses nothing" in n]


def test_a_scoped_override_that_excuses_an_offender_is_not_dead(repo: Repo, scratch: None) -> None:
    @check("scratch.files", "files")
    def _files(ctx: Context) -> Finding:
        bad = [p for p in ("a.txt", "b.txt") if ctx.excused("scratch.files", p) is None]
        return failing(", ".join(bad), "fix") if bad else passing("all excused")

    _scoped(repo, "scratch.files", "a.txt")
    assert _dead_notices(repo) == []


def test_a_scoped_override_no_offender_matches_is_named(repo: Repo, scratch: None) -> None:
    @check("scratch.files", "files")
    def _files(ctx: Context) -> Finding:
        return passing("nothing") if ctx.excused("scratch.files", "a.txt") is None else passing("excused")

    _scoped(repo, "scratch.files", "gone/*.txt")
    assert any("scratch.files" in n and "gone/*.txt" in n for n in _dead_notices(repo))


def test_a_scoped_override_on_a_check_that_never_asks_is_named(repo: Repo, scratch: None) -> None:
    @check("scratch.deaf", "never consults overrides")
    def _deaf(_ctx: object) -> Finding:
        return failing("red", "fix")

    _scoped(repo, "scratch.deaf", "x.py")
    assert any("scratch.deaf" in n for n in _dead_notices(repo))


def test_a_detection_override_for_a_path_that_is_gone_is_named(repo: Repo) -> None:
    repo.write("scripts/here.sh", "#!/bin/sh\n")
    _scoped(repo, "detection", "scripts/gone.sh")
    assert any("scripts/gone.sh" in n for n in _dead_notices_all(repo))
    _scoped(repo, "detection", "scripts/here.sh")
    assert _dead_notices_all(repo) == []


def _dead_notices_all(repo: Repo) -> list[str]:
    return [n for n in run(repo.root, env=repo.env, today=date(2026, 11, 20)).notices if "excuses nothing" in n]


def test_an_override_naming_no_checkpoint_the_run_judged_is_named(repo: Repo, scratch: None) -> None:
    @check("scratch.real", "real")
    def _real(_ctx: object) -> Finding:
        return failing("red", "fix")

    _override(repo, "scratch.renamed-away")
    result = run(repo.root, env=repo.env, today=date(2026, 11, 20))
    assert any("scratch.renamed-away" in n and "names no checkpoint" in n for n in result.notices)


def test_an_override_for_a_checkpoint_skipped_without_audit_is_not_an_orphan(repo: Repo, scratch: None) -> None:
    @check("scratch.slow", "audit only", audit_only=True)
    def _slow(_ctx: object) -> Finding:
        return failing("red", "fix")

    _override(repo, "scratch.slow")
    assert not any("names no checkpoint" in n for n in run(repo.root, env=repo.env, today=date(2026, 11, 20)).notices)
    assert not any("names no checkpoint" in n for n in run(repo.root, concern="scratch", env=repo.env, today=date(2026, 11, 20)).notices)
