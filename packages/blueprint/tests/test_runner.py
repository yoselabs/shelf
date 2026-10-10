"""The runner and the report: verdicts, overrides, refused results, exit codes, the set hash."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

import pytest
from blueprint import report
from blueprint.__main__ import main
from blueprint.model import REGISTRY, Check, Finding, Profile, Verdict, check, failing, not_checked, passing
from blueprint.runner import Row, Run, active, run, set_hash

if TYPE_CHECKING:
    from collections.abc import Iterator

    from blueprint.testing import Repo


@pytest.fixture
def scratch_concern() -> Iterator[None]:
    """Checks registered by the test live only for the test."""
    before = list(REGISTRY)
    yield
    REGISTRY[:] = before


@pytest.mark.parametrize(
    ("finding", "verdict"),
    [
        (passing("ok"), Verdict.PASSING),
        (failing("bad", "fix"), Verdict.FAILING),
        (Finding(set_up=False, working=None, evidence="absent"), Verdict.NOT_SET_UP),
        (not_checked("no tool"), Verdict.NOT_CHECKED),
        (Finding(set_up=True, working=None, evidence="half"), Verdict.NOT_CHECKED),
        (Finding(set_up=None, working=None, evidence="n/a", applicable=False), Verdict.NOT_APPLICABLE),
    ],
)
def test_the_two_answers_give_one_verdict(finding: Finding, verdict: Verdict) -> None:
    assert finding.verdict is verdict


def test_a_crashing_check_and_an_evidence_free_pass_are_both_not_checked(repo: Repo, scratch_concern: None) -> None:
    @check("scratch.crash", "crashes")
    def _crash(_ctx: object) -> Finding:
        msg = "boom"
        raise RuntimeError(msg)

    @check("scratch.silent", "passes with nothing to show")
    def _silent(_ctx: object) -> Finding:
        return passing("  ")

    rows = {r.id: r for r in run(repo.root, concern="scratch", env=repo.env).rows}
    assert rows["scratch.crash"].verdict is Verdict.NOT_CHECKED
    assert "boom" in rows["scratch.crash"].evidence
    assert rows["scratch.silent"].verdict is Verdict.NOT_CHECKED


def test_an_override_passes_until_it_expires(repo: Repo, scratch_concern: None) -> None:
    @check("scratch.red", "always red")
    def _red(_ctx: object) -> Finding:
        return failing("red", "nothing")

    repo.write(
        "docs/blueprint/blueprint.toml",
        '[[override]]\nid = "scratch.red"\ncode = "not-applicable"\nreason = "no CI by design"\nexpires = 2027-01-01\n',
    )
    before = run(repo.root, concern="scratch", env=repo.env, today=date(2026, 12, 31)).rows[0]
    after = run(repo.root, concern="scratch", env=repo.env, today=date(2027, 1, 2)).rows[0]
    assert before.verdict is Verdict.PASSING
    assert "no CI by design" in before.evidence
    assert after.verdict is Verdict.FAILING
    assert "expired" in after.evidence


def test_an_override_with_an_unknown_code_does_not_count(repo: Repo, scratch_concern: None) -> None:
    @check("scratch.red", "always red")
    def _red(_ctx: object) -> Finding:
        return failing("red", "nothing")

    repo.write("docs/blueprint/blueprint.toml", '[[override]]\nid = "scratch.red"\ncode = "because"\nreason = "x"\nexpires = 2099-01-01\n')
    assert run(repo.root, concern="scratch", env=repo.env).rows[0].verdict is Verdict.FAILING


def _row(verdict: Verdict) -> Row:
    return Row("x.y", "x", "s", verdict, None, None, "e", "", report.FixedBy.AGENT)


@pytest.mark.parametrize(
    ("verdicts", "code"),
    [
        ([Verdict.PASSING, Verdict.NOT_APPLICABLE], 0),
        ([Verdict.PASSING, Verdict.NOT_CHECKED], 2),
        ([Verdict.NOT_CHECKED, Verdict.FAILING], 1),
        ([Verdict.NOT_SET_UP], 1),
    ],
)
def test_exit_code_never_passes_what_was_not_checked(verdicts: list[Verdict], code: int) -> None:
    profile = Profile("application", (), (), (), None)
    assert Run(profile, "h", tuple(_row(v) for v in verdicts), ()).exit_code == code


def test_the_set_hash_moves_when_a_check_is_versioned() -> None:
    a = Check("x.a", "x", "s", run=lambda _c: passing("e"))
    b = Check("x.b", "x", "s", run=lambda _c: passing("e"))
    b2 = Check("x.b", "x", "s", run=lambda _c: passing("e"), version=2)
    assert set_hash([a, b]) == set_hash([b, a])
    assert set_hash([a, b]) != set_hash([a, b2])


def test_checks_are_selected_by_profile() -> None:
    no_tracker = Profile("application", (), (), ("python-uv",), None)
    beads = Profile("application", (), (), ("python-uv",), "beads")
    assert "backlog.strict-config" not in {c.id for c in active(no_tracker)}
    assert "backlog.strict-config" in {c.id for c in active(beads)}


def test_the_profile_reads_stacks_and_takes_declared_values(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    repo.write("uv.lock", "")
    repo.write("src/App/App.csproj", "<Project/>")
    repo.write("docs/blueprint/blueprint.toml", '[profile]\nkind = "application"\nsurfaces = ["cli"]\ntraits = ["stores-data"]\n')
    profile = run(repo.root, env=repo.env).profile
    assert profile.stacks == ("python-uv", "dotnet")
    assert profile.surfaces == ("cli",)
    assert profile.traits == ("stores-data",)


def test_write_produces_one_table_per_concern(repo: Repo) -> None:
    result = run(repo.root, env=repo.env)
    paths = report.write(result, repo.root, date(2026, 10, 10))
    assert {p.name for p in paths} == {"README.md", "gate.md", "backlog.md", "stack.md", "agents.md"}
    text = (repo.root / "docs/blueprint/gate.md").read_text()
    assert "| | checkpoint | set up | working | evidence | remediation | fixed by |" in text
    assert "`gate.one-command`" in text


def test_the_cli_prints_json_and_exits_with_the_runs_code(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["check", "--repo", str(repo.root), "--json"])
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert code == 1
    assert {r["id"] for r in rows} >= {"gate.one-command", "backlog.tracker"}


def test_the_gate_form_lists_only_what_is_not_passing(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    main(["check", "--repo", str(repo.root), "--gate"])
    out = capsys.readouterr().out
    assert "gate.one-command -- not set up" in out
    assert out.strip().splitlines()[-1].startswith("blueprint: ")
