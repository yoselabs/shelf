"""The runner and the report: verdicts, overrides, refused results, exit codes, the set hash."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import date
from typing import TYPE_CHECKING

import pytest
from blueprint import report
from blueprint.__main__ import main
from blueprint.model import REGISTRY, Check, Finding, Profile, Verdict, check, failing, not_checked, passing
from blueprint.report import clip
from blueprint.runner import Row, Run, active, run, set_hash

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

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
    concerns = ("gate", "backlog", "knowledge", "secrets", "stack", "agents")
    assert {p.name for p in paths} == {"README.md", "checkpoints.txt", *(f"{c}.md" for c in concerns)}
    text = (repo.root / "docs/blueprint/gate.md").read_text()
    assert "| | checkpoint | set up | working | evidence | remediation | fixed by |" in text
    assert "`gate.one-command`" in text


def test_write_removes_the_report_of_a_concern_that_no_longer_applies(repo: Repo) -> None:
    result = run(repo.root, env=repo.env)
    report.write(result, repo.root, date(2026, 10, 10))
    stale = repo.root / "docs/blueprint/stack-shell.md"
    stale.write_text(
        "# Blueprint: stack/shell (Stack-specific)\n\nWritten by `blueprint check --write` on 2026-10-09; rewritten on every run.\n"
    )
    own = repo.root / "docs/blueprint/notes.md"
    own.write_text("# Notes the owner keeps here\n")
    report.write(result, repo.root, date(2026, 10, 10))
    assert not stale.exists()
    assert own.exists()


def test_a_run_of_one_concern_keeps_the_other_reports(repo: Repo) -> None:
    report.write(run(repo.root, env=repo.env), repo.root, date(2026, 10, 10))
    report.write(run(repo.root, concern="gate", env=repo.env), repo.root, date(2026, 10, 10), prune=False)
    assert (repo.root / "docs/blueprint/knowledge.md").exists()


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


def test_the_summary_without_audit_says_it_omits_audit_rows_and_matches_the_readme_with_it(
    repo: Repo, scratch_concern: None, capsys: pytest.CaptureFixture[str]
) -> None:
    @check("scratch.slow", "needs this clone's state", audit_only=True)
    def _slow(_ctx: object) -> Finding:
        return failing("red only under audit", "fix it")

    root = str(repo.root)
    main(["check", "--repo", root, "--concern", "scratch", "--audit", "--write"])
    capsys.readouterr()
    readme = (repo.root / "docs/blueprint/README.md").read_text()

    main(["check", "--repo", root, "--concern", "scratch", "--audit", "--summary"])
    audited = capsys.readouterr().out
    assert audited.strip() in readme
    assert "| scratch | 0 | 1 |" in audited

    main(["check", "--repo", root, "--concern", "scratch", "--summary"])
    bare = capsys.readouterr().out
    assert "| scratch |" not in bare
    assert "audit-only checkpoints not run: 1" in bare
    assert "--audit" in bare
    assert "not run" not in audited


def test_a_checkpoint_new_since_the_last_audit_warns_but_does_not_fail_the_gate(repo: Repo) -> None:
    first = run(repo.root, env=repo.env)
    report.write(first, repo.root, date(2026, 10, 10))
    accepted = repo.root / "docs/blueprint/checkpoints.txt"
    failing_ids = [r.id for r in first.rows if r.verdict in {Verdict.FAILING, Verdict.NOT_SET_UP}]
    assert failing_ids
    kept = [line for line in accepted.read_text().splitlines() if not line.startswith(f"{failing_ids[0]}@")]
    accepted.write_text("\n".join(kept) + "\n")
    later = run(repo.root, env=repo.env)
    new = [r for r in later.rows if r.new]
    assert [r.id for r in new] == [failing_ids[0]]
    assert "new since the last audit" in report.gate(later)


def test_without_an_audit_record_every_checkpoint_is_enforced(repo: Repo) -> None:
    assert not any(r.new for r in run(repo.root, env=repo.env).rows)


def test_new_rows_alone_do_not_fail_the_exit_code(repo: Repo) -> None:
    result = run(repo.root, env=repo.env)
    report.write(result, repo.root, date(2026, 10, 10))
    (repo.root / "docs/blueprint/checkpoints.txt").write_text("")
    assert run(repo.root, env=repo.env).exit_code in {0, 2}


def test_an_audit_from_before_the_record_counts_as_an_empty_record(repo: Repo) -> None:
    repo.write("docs/blueprint/README.md", "# Blueprint\n")
    rows = run(repo.root, env=repo.env).rows
    assert all(r.new for r in rows if r.verdict is not Verdict.PASSING)


def _adr(number: str, status: str) -> str:
    return (
        f"---\nid: {number}\ntitle: Builds on owner machines\nstatement: No CI; the gate runs on the owner's machines.\n"
        f"concerns: [gate]\nstatus: {status}\ndecided_by: owner\nupdated: 2026-10-11\n---\n# {number}\n"
    )


def _red_override(repo: Repo, fields: str) -> None:
    repo.write("docs/blueprint/blueprint.toml", f'[[override]]\nid = "scratch.red"\ncode = "not-applicable"\n{fields}\n')


@pytest.fixture
def red_check(scratch_concern: None) -> None:
    @check("scratch.red", "always red")
    def _red(_ctx: object) -> Finding:
        return failing("red", "nothing")


def test_an_override_backed_by_an_accepted_adr_needs_no_expiry(repo: Repo, red_check: None) -> None:
    repo.write("docs/adr/0003-builds-on-owner-machines.md", _adr("0003", "accepted"))
    _red_override(repo, 'reason = "no CI by decision"\nadr = "0003"')
    result = run(repo.root, concern="scratch", env=repo.env, today=date(2099, 1, 1))
    assert result.rows[0].verdict is Verdict.PASSING
    assert "ADR 0003" in result.rows[0].evidence
    assert result.problems == ()


@pytest.mark.parametrize(
    ("adr_file", "fields", "named"),
    [
        (None, 'reason = "r"\nadr = "0003"', "ADR 0003"),
        (("0003", "proposed"), 'reason = "r"\nadr = "0003"', "not accepted"),
        (("0003", "superseded"), 'reason = "r"\nadr = "0003"', "not accepted"),
        (None, 'reason = "r"', "expires"),
        (None, 'reason = "  "\nexpires = 2099-01-01', "reason"),
        (None, 'reason = "r"\nadr = "3"', "NNNN"),
    ],
)
def test_an_unjustified_override_is_a_reported_problem_and_does_not_count(
    repo: Repo, red_check: None, adr_file: tuple[str, str] | None, fields: str, named: str
) -> None:
    if adr_file:
        repo.write(f"docs/adr/{adr_file[0]}-x.md", _adr(*adr_file))
    _red_override(repo, fields)
    result = run(repo.root, concern="scratch", env=repo.env)
    assert result.rows[0].verdict is Verdict.FAILING
    assert any(named in p for p in result.problems), result.problems
    assert result.exit_code == 1


def test_an_expiring_override_with_a_reason_stays_as_before(repo: Repo, red_check: None) -> None:
    _red_override(repo, 'reason = "r"\nexpires = 2099-01-01')
    result = run(repo.root, concern="scratch", env=repo.env, today=date(2026, 10, 11))
    assert result.rows[0].verdict is Verdict.PASSING
    assert "until 2099-01-01" in result.rows[0].evidence
    assert result.problems == ()


def _ignore(repo: Repo, fields: str) -> None:
    repo.write("docs/blueprint/blueprint.toml", f'[[profile.ignore]]\npath = "prototype"\n{fields}\n')
    repo.write("prototype/spike/Spike.csproj", "<Project/>")


def test_a_declared_throwaway_dir_does_not_set_the_stack(repo: Repo) -> None:
    _ignore(repo, 'reason = "throwaway spikes bind nothing"\nexpires = 2099-01-01')
    result = run(repo.root, env=repo.env)
    assert result.profile.stacks == ()
    assert result.problems == ()


def test_the_same_dir_without_the_ignore_sets_dotnet_and_names_the_file(repo: Repo) -> None:
    repo.write("prototype/spike/Spike.csproj", "<Project/>")
    profile = run(repo.root, env=repo.env).profile
    assert profile.stacks == ("dotnet",)
    assert dict(profile.stack_files)["dotnet"] == "prototype/spike/Spike.csproj"


@pytest.mark.parametrize(
    ("fields", "named"),
    [("expires = 2099-01-01", "reason"), ('reason = "r"', "expires"), ('reason = "r"\nadr = "0009"', "ADR 0009")],
)
def test_an_unjustified_ignore_is_a_problem_and_ignores_nothing(repo: Repo, fields: str, named: str) -> None:
    _ignore(repo, fields)
    result = run(repo.root, env=repo.env)
    assert result.profile.stacks == ("dotnet",)
    assert any("ignore" in p and named in p for p in result.problems), result.problems


def test_an_override_needs_no_code_and_a_missing_decided_by_reads_unknown(repo: Repo, red_check: None) -> None:
    repo.write("docs/blueprint/blueprint.toml", '[[override]]\nid = "scratch.red"\nreason = "r"\nexpires = 2099-01-01\n')
    result = run(repo.root, concern="scratch", env=repo.env)
    assert result.rows[0].verdict is Verdict.PASSING
    assert result.problems == ()
    assert [(o.id, o.decided_by) for o in result.overrides] == [("scratch.red", "unknown")]


def test_a_scoped_override_leaves_the_row_to_its_check(repo: Repo, red_check: None) -> None:
    repo.write(
        "docs/blueprint/blueprint.toml", '[[override]]\nid = "scratch.red"\nscope = "src/x.py"\nreason = "r"\nexpires = 2099-01-01\n'
    )
    assert run(repo.root, concern="scratch", env=repo.env).rows[0].verdict is Verdict.FAILING


@pytest.mark.parametrize(
    ("fields", "named"), [("expires = 2099-01-01", "reason"), ('reason = " "\nexpires = 2099-01-01', "reason"), ('reason = "r"', "expires")]
)
def test_a_scoped_override_is_justified_like_any_other(repo: Repo, red_check: None, fields: str, named: str) -> None:
    repo.write("docs/blueprint/blueprint.toml", f'[[override]]\nid = "scratch.red"\nscope = "src/x.py"\n{fields}\n')
    result = run(repo.root, concern="scratch", env=repo.env)
    assert any(named in p for p in result.problems), result.problems
    assert result.exit_code == 1


def test_an_unknown_decided_by_is_a_problem(repo: Repo, red_check: None) -> None:
    repo.write(
        "docs/blueprint/blueprint.toml", '[[override]]\nid = "scratch.red"\nreason = "r"\nexpires = 2099-01-01\ndecided_by = "bot"\n'
    )
    assert any("decided_by" in p for p in run(repo.root, concern="scratch", env=repo.env).problems)


def _detection(repo: Repo, fields: str) -> None:
    repo.write("docs/blueprint/blueprint.toml", f'[[override]]\nid = "detection"\nscope = "prototype"\n{fields}\n')
    repo.write("prototype/spike/Spike.csproj", "<Project/>")


def test_a_detection_override_skips_its_path(repo: Repo) -> None:
    _detection(repo, 'reason = "throwaway spikes bind nothing"\nexpires = 2099-01-01')
    result = run(repo.root, env=repo.env)
    assert result.profile.stacks == ()
    assert result.problems == ()
    assert result.notices == ()


@pytest.mark.parametrize(("fields", "named"), [("expires = 2099-01-01", "reason"), ('reason = "r"', "expires")])
def test_an_unjustified_detection_override_skips_nothing(repo: Repo, fields: str, named: str) -> None:
    _detection(repo, fields)
    result = run(repo.root, env=repo.env)
    assert result.profile.stacks == ("dotnet",)
    assert any(named in p for p in result.problems), result.problems


def test_a_detection_override_naming_one_file_keeps_that_file_out_of_the_stack(repo: Repo) -> None:
    for name in ("tools/a.sh", "scripts/b.sh"):
        repo.write(name, "#!/usr/bin/env bash\nset -euo pipefail\n" + "echo x\n" * 12, executable=True)
    repo.write(
        "docs/blueprint/blueprint.toml",
        '[[profile.ignore]]\npath = "tools/a.sh"\nreason = "r"\nexpires = 2099-01-01\n'
        '[[override]]\nid = "detection"\nscope = "scripts/b.sh"\nreason = "r"\nexpires = 2099-01-01\n',
    )
    result = run(repo.root, env=repo.env)
    assert "shell" not in result.profile.stacks
    assert result.problems == ()
    assert len(result.notices) == 1
    assert 'scope = "tools/a.sh"' in result.notices[0]


def test_a_detection_override_needs_a_scope(repo: Repo) -> None:
    repo.write("docs/blueprint/blueprint.toml", '[[override]]\nid = "detection"\nreason = "r"\nexpires = 2099-01-01\n')
    assert any("scope" in p for p in run(repo.root, env=repo.env).problems)


def test_an_old_ignore_still_works_and_is_reported_with_its_replacement(repo: Repo) -> None:
    _ignore(repo, 'reason = "throwaway spikes bind nothing"\nexpires = 2099-01-01')
    result = run(repo.root, env=repo.env)
    assert result.profile.stacks == ()
    assert result.problems == ()
    (notice,) = result.notices
    assert "[[profile.ignore]]" in notice
    assert "move it to an [[override]] in docs/blueprint/blueprint.toml" in notice
    for line in ('id = "detection"', 'scope = "prototype"', 'reason = "throwaway spikes bind nothing"', "expires = 2099-01-01"):
        assert line in notice
    text = report.markdown(result)
    assert "[[profile.ignore]]" in text
    assert '```toml\n[[override]]\nid = "detection"\nscope = "prototype"' in text
    assert notice in json.loads(report.as_json(result))["notices"]


def _two_overrides(repo: Repo) -> None:
    repo.write(
        "docs/blueprint/blueprint.toml",
        '[[override]]\nid = "scratch.red"\nreason = "no CI by design"\ndecided_by = "owner"\nadr = "0003"\n\n'
        '[[override]]\nid = "stack.shell.strict-mode"\nscope = "tools/probe.sh"\nreason = "a probe"\nexpires = 2099-01-01\n',
    )
    repo.write("docs/adr/0003-x.md", _adr("0003", "accepted"))


def test_the_markdown_report_lists_every_override_before_the_facts(repo: Repo, red_check: None) -> None:
    _two_overrides(repo)
    text = report.markdown(run(repo.root, concern="scratch", env=repo.env))
    assert text.index("## Overrides") < text.index("## Facts and evidence")
    assert text.index("engine:") < text.index("## Overrides")
    block = text[text.index("## Overrides") : text.index("## Facts and evidence")]
    assert "`scratch.red`" in block
    assert "owner" in block
    assert "ADR 0003" in block
    assert "`stack.shell.strict-mode`" in block
    assert "tools/probe.sh" in block
    assert "unknown" in block
    assert "until 2099-01-01" in block
    assert "a probe" in block


def test_the_markdown_report_says_so_when_there_are_no_overrides(repo: Repo) -> None:
    text = report.markdown(run(repo.root, concern="gate", env=repo.env))
    assert "## Overrides\n\nnone" in text


def test_the_json_report_lists_the_same_overrides(repo: Repo, red_check: None) -> None:
    _two_overrides(repo)
    data = json.loads(report.as_json(run(repo.root, concern="scratch", env=repo.env)))
    assert data["overrides"] == [
        {
            "id": "scratch.red",
            "scope": "",
            "reason": "no CI by design",
            "decided_by": "owner",
            "expires": None,
            "adr": "0003",
            "problem": None,
        },
        {
            "id": "stack.shell.strict-mode",
            "scope": "tools/probe.sh",
            "reason": "a probe",
            "decided_by": "unknown",
            "expires": "2099-01-01",
            "adr": "",
            "problem": None,
        },
    ]


def test_a_written_report_names_the_engine_and_the_scope(repo: Repo) -> None:
    result = run(repo.root, concern="gate", env=repo.env)
    report.write(result, repo.root, date(2026, 10, 11))
    for name in ("README.md", "gate.md"):
        head = (repo.root / "docs/blueprint" / name).read_text().split("\n\n")[:6]
        text = "\n".join(head)
        assert f"`{result.set_hash}`" in text
        assert re.search(r"engine: (shelf `[0-9a-f]{7,}`|blueprint \d)", text)
        assert "concerns checked: gate" in text
        assert "not run:" in text


def test_the_summary_cuts_a_long_first_to_fix_at_a_word_and_marks_the_cut() -> None:
    # homelab (shelf-3oe): cells ended mid-word ("validation.on-", "the Nix that r").
    text = "flake.lock committed beside every flake.nix (pins nixpkgs and every input); the Nix that runs the gate is pinned"
    cut = clip(text, 90)
    assert len(cut) <= 90
    assert cut.endswith("…")
    assert text.startswith(cut.removesuffix("…").rstrip())
    assert text[len(cut.removesuffix("…").rstrip())] == " "
    assert clip("short", 90) == "short"


def test_a_hooks_git_variables_never_reach_the_repo_they_name(repo: Repo, tmp_path: Path) -> None:
    # 2026-10-12: under a pre-push hook in a worktree, the sandbox `git init` behind a gate row ran against the
    # hook's GIT_DIR and set core.bare on the shelf itself.
    victim = tmp_path / "victim"
    git = ["git", "-c", "user.email=t@invalid", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", str(victim)], check=True)
    subprocess.run([*git, "-C", str(victim), "commit", "-q", "--allow-empty", "-m", "root"], check=True)
    subprocess.run(["git", "-C", str(victim), "worktree", "add", "-q", str(tmp_path / "wt")], check=True)
    before = (victim / ".git/config").read_text()
    repo.write(".gitignore", ".worktrees/\n")
    repo.commit()
    # homelab saw the other symptom: with the work tree inherited too, the init wrote core.worktree instead.
    leaked = {**repo.env, "GIT_DIR": str(victim / ".git/worktrees/wt"), "GIT_WORK_TREE": str(tmp_path / "wt")}
    run(repo.root, env=leaked)
    assert (victim / ".git/config").read_text() == before
