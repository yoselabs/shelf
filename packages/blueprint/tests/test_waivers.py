"""ADR 0018: the pin decides the checkpoints; a dated waiver in the repo is the only way to wait."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from blueprint import report
from blueprint.model import REGISTRY, Finding, Verdict, check, failing, not_checked, passing
from blueprint.runner import Run, run

if TYPE_CHECKING:
    from collections.abc import Iterator

    from blueprint.testing import Repo

TODAY = date(2026, 12, 1)


@pytest.fixture
def red_check() -> Iterator[None]:
    before = list(REGISTRY)

    @check("scratch.red", "always red")
    def _red(_ctx: object) -> Finding:
        return failing("red", "nothing")

    yield
    REGISTRY[:] = before


def _waive(repo: Repo, fields: str, wid: str = "scratch.red") -> None:
    since = "" if "since" in fields else 'since = "2026-12-01"\n'
    repo.write("docs/blueprint/blueprint.toml", f'[[tool.blueprint.waivers]]\nid = "{wid}"\n{since}{fields}\n')


def _scratch(repo: Repo) -> Run:
    return run(repo.root, concern="scratch", env=repo.env, today=TODAY)


def test_a_waiver_passes_the_row_and_shows_the_days_left(repo: Repo, red_check: None) -> None:
    _waive(repo, 'reason = "fixed next release"\nuntil = "2026-12-31"')
    result = _scratch(repo)
    assert result.rows[0].verdict is Verdict.PASSING
    assert "waived until 2026-12-31 (30 days left): fixed next release" in result.rows[0].evidence
    assert result.problems == ()
    assert any("waiver `scratch.red`" in n and "30 days left" in n for n in result.notices)
    assert result.exit_code == 0


def test_the_waiver_table_form_in_the_toml_also_loads(repo: Repo, red_check: None) -> None:
    repo.write(
        "docs/blueprint/blueprint.toml",
        '[tool.blueprint]\nwaivers = [{ id = "scratch.red", reason = "r", since = 2026-12-01, until = 2026-12-31 }]\n',
    )
    assert _scratch(repo).rows[0].verdict is Verdict.PASSING


def test_an_expired_waiver_fails_the_run_and_excuses_nothing(repo: Repo, red_check: None) -> None:
    _waive(repo, 'reason = "r"\nsince = "2026-10-01"\nuntil = "2026-11-30"')
    result = _scratch(repo)
    assert result.rows[0].verdict is Verdict.FAILING
    assert any("expired 2026-11-30" in p for p in result.problems)
    assert result.exit_code == 1


def test_a_waiver_on_its_last_day_still_holds(repo: Repo, red_check: None) -> None:
    _waive(repo, 'reason = "r"\nuntil = "2026-12-01"')
    result = _scratch(repo)
    assert result.rows[0].verdict is Verdict.PASSING
    assert "0 days left" in result.rows[0].evidence


@pytest.mark.parametrize("reason", ['reason = ""', 'reason = "   "', ""])
def test_a_waiver_without_a_reason_fails(repo: Repo, red_check: None, reason: str) -> None:
    _waive(repo, f'{reason}\nuntil = "2026-12-31"')
    result = _scratch(repo)
    assert result.rows[0].verdict is Verdict.FAILING
    assert any("no reason" in p for p in result.problems)


def test_a_waiver_more_than_ninety_days_out_fails(repo: Repo, red_check: None) -> None:
    _waive(repo, 'reason = "r"\nuntil = "2027-03-02"')  # 91 days
    result = _scratch(repo)
    assert result.rows[0].verdict is Verdict.FAILING
    assert any("90 days" in p for p in result.problems)


def test_a_waiver_exactly_ninety_days_out_holds(repo: Repo, red_check: None) -> None:
    _waive(repo, 'reason = "r"\nuntil = "2027-03-01"')
    assert _scratch(repo).rows[0].verdict is Verdict.PASSING


@pytest.mark.parametrize("until", ["", 'until = "soon"', "until = 5"])
def test_a_waiver_without_a_usable_date_fails(repo: Repo, red_check: None, until: str) -> None:
    _waive(repo, f'reason = "r"\n{until}')
    result = _scratch(repo)
    assert result.rows[0].verdict is Verdict.FAILING
    assert any("until" in p for p in result.problems)


def test_a_waiver_for_an_unknown_checkpoint_fails(repo: Repo) -> None:
    _waive(repo, 'reason = "r"\nuntil = "2026-12-31"', wid="gate.no-such-row")
    result = run(repo.root, env=repo.env, today=TODAY)
    assert any("gate.no-such-row" in p and "not a checkpoint" in p for p in result.problems)
    assert result.exit_code == 1


def test_a_waiver_for_a_known_checkpoint_the_repo_does_not_run_is_not_unknown(repo: Repo) -> None:
    _waive(repo, 'reason = "r"\nuntil = "2026-12-31"', wid="stack.python-uv.linter")
    assert not [p for p in run(repo.root, env=repo.env, today=TODAY).problems if "not a checkpoint" in p]


def test_a_new_row_fails_without_a_waiver_whatever_an_old_baseline_says(repo: Repo) -> None:
    repo.write("docs/blueprint/checkpoints.txt", "")
    repo.write("docs/blueprint/README.md", "# Blueprint\n")
    rows = run(repo.root, env=repo.env, today=TODAY).rows
    bad = [r for r in rows if r.verdict in {Verdict.FAILING, Verdict.NOT_SET_UP}]
    assert bad
    assert not hasattr(bad[0], "new")
    assert "🆕" not in report.gate(run(repo.root, env=repo.env, today=TODAY))


def test_write_no_longer_records_a_baseline(repo: Repo) -> None:
    paths = report.write(run(repo.root, env=repo.env), repo.root, TODAY)
    assert "checkpoints.txt" not in {p.name for p in paths}
    assert not (repo.root / "docs/blueprint/checkpoints.txt").exists()


def test_a_datetime_until_parses_instead_of_crashing(repo: Repo, red_check: None) -> None:
    _waive(repo, 'reason = "r"\nuntil = 2026-12-31T00:00:00Z')
    result = _scratch(repo)
    assert result.rows[0].verdict is Verdict.PASSING
    assert "until 2026-12-31" in result.rows[0].evidence


def test_a_waiver_without_since_fails(repo: Repo, red_check: None) -> None:
    repo.write("docs/blueprint/blueprint.toml", '[[tool.blueprint.waivers]]\nid = "scratch.red"\nreason = "r"\nuntil = "2026-12-31"\n')
    result = _scratch(repo)
    assert result.rows[0].verdict is Verdict.FAILING
    assert any("since" in p for p in result.problems)


def test_a_renewal_cannot_stretch_past_ninety_days_from_since(repo: Repo, red_check: None) -> None:
    _waive(repo, 'reason = "r"\nsince = "2026-10-01"\nuntil = "2027-01-15"')  # 106 days from since, 45 from today
    result = _scratch(repo)
    assert result.rows[0].verdict is Verdict.FAILING
    assert any("since" in p and "90" in p for p in result.problems)


def test_a_since_in_the_future_or_after_until_fails(repo: Repo, red_check: None) -> None:
    _waive(repo, 'reason = "r"\nsince = "2026-12-20"\nuntil = "2026-12-31"')
    result = _scratch(repo)
    assert result.rows[0].verdict is Verdict.FAILING
    assert any("future" in p for p in result.problems)


def test_a_waiver_does_not_turn_not_checked_into_a_pass(repo: Repo) -> None:
    before = list(REGISTRY)

    @check("scratch.blind", "cannot judge")
    def _blind(_ctx: object) -> Finding:
        return not_checked("tool missing")

    try:
        _waive(repo, 'reason = "r"\nuntil = "2026-12-31"', wid="scratch.blind")
        row = _scratch(repo).rows[0]
    finally:
        REGISTRY[:] = before
    assert row.verdict is Verdict.NOT_CHECKED
    assert "waiver ignored" in row.evidence


def test_a_waiver_on_a_passing_row_is_reported_unused(repo: Repo) -> None:
    before = list(REGISTRY)

    @check("scratch.green", "always green")
    def _green(_ctx: object) -> Finding:
        return passing("fine")

    try:
        _waive(repo, 'reason = "r"\nuntil = "2026-12-31"', wid="scratch.green")
        result = run(repo.root, env=repo.env, today=TODAY)
    finally:
        REGISTRY[:] = before
    assert any("waiver `scratch.green` is unused" in n for n in result.notices)


def test_a_waiver_in_a_toml_the_audit_does_not_read_is_named(repo: Repo, red_check: None) -> None:
    repo.write("sub/pyproject.toml", '[[tool.blueprint.waivers]]\nid = "scratch.red"\n')
    result = run(repo.root, env=repo.env, today=TODAY)
    assert any("sub/pyproject.toml" in n and "not read" in n for n in result.notices)
