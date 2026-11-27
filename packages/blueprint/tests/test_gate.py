"""Gate checkpoints: each seen passing on a sound repo and failing on a planted violation."""

from __future__ import annotations

import itertools
import shutil
import subprocess
from datetime import date
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from blueprint.concerns.gate import gate_clone
from blueprint.init import RECIPES
from blueprint.model import FixedBy, Verdict
from blueprint.report import gate as gate_report
from blueprint.report import markdown as markdown_report
from blueprint.runner import run, run_audit

if TYPE_CHECKING:
    from pathlib import Path

    from blueprint.testing import Repo


def _verdict(repo: Repo, check_id: str, *, audit: bool = True) -> tuple[Verdict, str]:
    rows = {r.id: r for r in (run_audit if audit else run)(repo.root, concern="gate", env=repo.env).rows}
    return rows[check_id].verdict, rows[check_id].evidence


def test_one_command_passes_when_check_resolves(repo: Repo) -> None:
    repo.write("justfile", "check: lint\nlint:\n\ttrue\n")
    assert _verdict(repo, "gate.one-command")[0] is Verdict.PASSING


def test_one_command_is_not_set_up_without_a_makefile(repo: Repo) -> None:
    assert _verdict(repo, "gate.one-command")[0] is Verdict.NOT_SET_UP


def test_one_command_fails_when_check_names_a_missing_target(repo: Repo) -> None:
    repo.write("justfile", "check: lint preset\nlint:\n\ttrue\n")
    verdict, evidence = _verdict(repo, "gate.one-command")
    assert verdict is Verdict.FAILING
    assert "preset" in evidence


def test_no_ci_passes_in_a_repo_without_github_actions(repo: Repo) -> None:
    repo.write(".github/dependabot.yml", "version: 2\n")
    repo.write(".github/CODEOWNERS", "* @owner\n")
    assert _verdict(repo, "gate.no-ci")[0] is Verdict.PASSING


@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/check.yml",
        ".github/workflows/release.yaml",
        ".github/actions/setup/action.yml",
        ".github/actions/setup/action.yaml",
    ],
)
def test_no_ci_fails_on_github_actions_config(repo: Repo, path: str) -> None:
    repo.write(path, "on: [push]\n")
    repo.write(".github/workflows/ignored.txt", "not a workflow\n")
    verdict, evidence = _verdict(repo, "gate.no-ci")
    assert verdict is Verdict.FAILING
    assert path in evidence
    assert "ignored.txt" not in evidence


def test_no_ci_is_excused_per_workflow_by_a_justified_override(repo: Repo) -> None:
    repo.write(".github/workflows/deploy.yml", "on: [push]\n")
    repo.write(".github/workflows/lint.yml", "on: [push]\n")
    repo.write(
        "docs/blueprint/blueprint.toml",
        '[[override]]\nid = "gate.no-ci"\nscope = ".github/workflows/deploy.yml"\nreason = "deploys the stack"\nexpires = 2099-01-01\n',
    )
    verdict, evidence = _verdict(repo, "gate.no-ci")
    assert verdict is Verdict.FAILING
    assert "lint.yml" in evidence
    assert "deploy.yml" not in evidence
    (repo.root / ".github/workflows/lint.yml").unlink()
    assert _verdict(repo, "gate.no-ci")[0] is Verdict.PASSING


def test_no_ci_remediation_deletes_and_never_silently_keeps_a_non_ci_duty(repo: Repo) -> None:
    repo.write(".github/workflows/publish.yml", "on: [push]\n")
    row = {r.id: r for r in run(repo.root, concern="gate", env=repo.env).rows}["gate.no-ci"]
    assert "delete" in row.remediation
    assert "local command" in row.remediation
    assert "owner decision" in row.remediation
    assert row.fixed_by is FixedBy.OWNER


def _audited_before_no_ci(repo: Repo) -> None:
    """A consumer audited when `gate.ci` existed: its record lists the removed checkpoints, not `gate.no-ci`."""
    repo.write("docs/blueprint/checkpoints.txt", "gate.ci@1\ngate.ci-no-manifest-edit@1\ngate.ci-green@1\n")
    repo.write("docs/blueprint/blueprint.toml", '[[override]]\nid = "gate.ci"\nreason = "no CI here"\nexpires = 2099-01-01\n')


def test_gate_no_ci_warns_new_in_a_consumer_audited_before_it_existed(repo: Repo) -> None:
    # ADR 0018: a checkpoint newer than the last audit only warns until the next audit takes it in.
    _audited_before_no_ci(repo)
    repo.write(".github/workflows/check.yml", "on: [push]\n")
    result = run(repo.root, concern="gate", env=repo.env)
    row = {r.id: r for r in result.rows}["gate.no-ci"]
    assert row.verdict is Verdict.FAILING
    assert row.new
    assert "gate.no-ci" in gate_report(result)


def test_the_brief_form_clips_long_evidence_and_points_to_the_full_report(repo: Repo) -> None:
    for n in range(6):  # the evidence lists every file: six long names pass 200 characters
        repo.write(f".github/workflows/{'x' * 60}{n}.yml", "on: [push]\n")
    result = run(repo.root, concern="gate", env=repo.env)
    brief = gate_report(result)
    line = next(ln for ln in brief.splitlines() if "gate.no-ci" in ln)
    assert "…" in line
    assert "x" * 60 + "5" not in brief
    assert "cut text: `blueprint check`" in brief
    assert "x" * 60 + "5" in markdown_report(result)


def test_a_leftover_override_of_a_removed_ci_checkpoint_is_a_notice_not_a_failure(repo: Repo) -> None:
    _audited_before_no_ci(repo)
    result = run(repo.root, env=repo.env)
    assert any("`gate.ci` names no checkpoint" in n for n in result.notices)
    assert not any("gate.ci" in p for p in result.problems)


def _recipe() -> str:
    return (RECIPES / "pre-commit-config.yaml").read_text()


def _prek_hook(repo: Repo, body: str = "# File generated by prek: https://github.com/j178/prek\n") -> None:
    repo.write_executable(".git/hooks/pre-commit", "#!/bin/sh\n" + body)


def test_the_recipe_passes_both_halves_with_beads(repo: Repo) -> None:
    repo.write(".beads/config.yaml", "")
    repo.write(".pre-commit-config.yaml", _recipe())
    _prek_hook(repo)
    assert _verdict(repo, "gate.hooks-recipe")[0] is Verdict.PASSING
    assert _verdict(repo, "gate.hooks-installed")[0] is Verdict.PASSING
    assert _backlog(repo, "backlog.hooks-recipe")[0] is Verdict.PASSING
    assert _backlog(repo, "backlog.hooks-installed")[0] is Verdict.PASSING


def _backlog(repo: Repo, row_id: str) -> tuple[Verdict, str]:
    row = next(r for r in run_audit(repo.root, concern="backlog", env=repo.env).rows if r.id == row_id)
    return row.verdict, row.evidence


def test_no_hook_config_is_not_set_up_with_the_recipe_as_auto_fix(repo: Repo) -> None:
    row = next(r for r in run_audit(repo.root, concern="gate", env=repo.env).rows if r.id == "gate.hooks-recipe")
    assert row.verdict is Verdict.NOT_SET_UP
    assert "blueprint init" in row.remediation
    assert row.fixed_by == "auto"


def test_a_config_missing_bds_events_fails(repo: Repo) -> None:
    repo.write(".beads/config.yaml", "")
    repo.write(".pre-commit-config.yaml", _recipe().replace("bd hooks run post-checkout", "true"))
    verdict, evidence = _backlog(repo, "backlog.hooks-recipe")
    assert verdict is Verdict.FAILING
    assert "post-checkout" in evidence


def test_a_second_hook_manager_fails(repo: Repo) -> None:
    repo.write(".pre-commit-config.yaml", _recipe())
    repo.write("lefthook.yml", "pre-commit: {}\n")
    verdict, evidence = _verdict(repo, "gate.hooks-recipe")
    assert verdict is Verdict.FAILING
    assert "lefthook" in evidence


def test_tracked_bd_hook_files_fail(repo: Repo) -> None:
    repo.write(".pre-commit-config.yaml", _recipe())
    repo.write(".beads/hooks/pre-commit", "#!/bin/sh\n")
    repo.commit()
    assert "tracked" in _backlog(repo, "backlog.hooks-recipe")[1]


def test_bd_injected_into_the_installed_hook_fails(repo: Repo) -> None:
    repo.write(".beads/config.yaml", "")
    _prek_hook(repo, "# File generated by prek\n# --- BEGIN BEADS INTEGRATION v1.1.2 ---\n")
    assert _verdict(repo, "gate.hooks-installed")[0] is Verdict.PASSING
    verdict, evidence = _backlog(repo, "backlog.hooks-installed")
    assert verdict is Verdict.FAILING
    assert "injected" in evidence


def test_a_hooks_path_fails_because_a_fresh_clone_runs_nothing(repo: Repo) -> None:
    _prek_hook(repo)
    repo.git("config", "core.hooksPath", str(repo.root / ".beads/hooks"))
    verdict, evidence = _verdict(repo, "gate.hooks-installed")
    assert verdict is Verdict.FAILING
    assert "fresh clone" in evidence


def test_a_hand_written_hook_is_not_prek(repo: Repo) -> None:
    _prek_hook(repo, "make lint\n")
    assert _verdict(repo, "gate.hooks-installed")[0] is Verdict.FAILING


def test_installed_hooks_are_left_out_of_the_gate_run(repo: Repo) -> None:
    assert "gate.hooks-installed" not in {r.id for r in run(repo.root, concern="gate", env=repo.env).rows}


def test_guard_scripts_pass_when_a_test_names_each(repo: Repo) -> None:
    repo.write("justfile", "check: guard\nguard:\n\tpython3 tools/no-secrets.py\n")
    repo.write("tools/no-secrets.py", "")
    repo.write("tests/test_no_secrets.py", "# runs tools/no_secrets against a planted secret\n")
    assert _verdict(repo, "gate.guards-have-red-tests")[0] is Verdict.PASSING


def test_guard_scripts_fail_when_one_has_no_test(repo: Repo) -> None:
    repo.write(
        "justfile", "check: guard\nguard:\n\t@g=tools/no-secrets.py; python3 $$g\nother:\n\tpython3 tools/untested-but-unreached.py\n"
    )
    repo.write("tools/no-secrets.py", "")
    repo.write("tools/untested-but-unreached.py", "")
    verdict, evidence = _verdict(repo, "gate.guards-have-red-tests")
    assert verdict is Verdict.FAILING
    assert "tools/no-secrets.py" in evidence
    assert "unreached" not in evidence


def test_guard_scripts_do_not_apply_when_check_runs_none(repo: Repo) -> None:
    repo.write("justfile", "check:\n\ttrue\n")
    assert _verdict(repo, "gate.guards-have-red-tests")[0] is Verdict.NOT_APPLICABLE


def test_clean_clone_is_audit_only_and_left_out_of_the_gate_run(repo: Repo) -> None:
    rows = run(repo.root, concern="gate", env=repo.env).rows
    assert "gate.clean-clone" not in {r.id for r in rows}


def test_clean_clone_passes_within_its_budget(repo: Repo) -> None:
    repo.write("justfile", "check:\n\ttrue\n")
    repo.write("docs/blueprint/blueprint.toml", "[settings]\nclean-clone-seconds = 60\n")
    repo.commit()
    assert _verdict(repo, "gate.clean-clone", audit=True)[0] is Verdict.PASSING


def _runaway_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """A clock that counts a second a call, so a real sub-second gate reads as over any budget."""
    ticks = itertools.count(step=1000)
    monkeypatch.setattr(gate_clone, "time", SimpleNamespace(monotonic=lambda: float(next(ticks))))


def test_clean_clone_over_budget_reports_this_machines_load_average(repo: Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    _runaway_clock(monkeypatch)
    repo.write("justfile", "check:\n\ttrue\n")
    repo.write("docs/blueprint/blueprint.toml", "[settings]\nclean-clone-seconds = 60\n")
    repo.commit()
    repo.fake_tool(repo.bin_dir / "uptime", " 12:00  up 2 days, 1 user, load averages: 2.31 2.05 1.90")
    verdict, evidence = _verdict(repo, "gate.clean-clone", audit=True)
    assert verdict is Verdict.FAILING
    assert "budget 60s" in evidence
    assert "2.31" in evidence


def test_clean_clone_over_budget_without_a_load_reading_still_fails_and_says_so(repo: Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    _runaway_clock(monkeypatch)
    repo.write("justfile", "check:\n\ttrue\n")
    repo.write("docs/blueprint/blueprint.toml", "[settings]\nclean-clone-seconds = 60\n")
    repo.commit()
    (repo.bin_dir / "uptime").write_text("#!/bin/sh\nexit 1\n")
    (repo.bin_dir / "uptime").chmod(0o755)
    verdict, evidence = _verdict(repo, "gate.clean-clone", audit=True)
    assert verdict is Verdict.FAILING
    assert "budget 60s" in evidence
    assert "load average unavailable" in evidence


def test_clean_clone_never_passes_on_an_uncommitted_file_and_names_it(repo: Repo) -> None:
    # HEAD fails, the working tree passes: the row says what to commit (a2kay, shelf-83g), and never passes on it.
    repo.write("justfile", "check:\n\ttest -f generated.txt\n")
    repo.commit()
    repo.write("generated.txt", "only on this machine")
    verdict, evidence = _verdict(repo, "gate.clean-clone", audit=True)
    assert verdict is Verdict.NOT_CHECKED
    assert "commit to verify" in evidence
    assert "generated.txt" in evidence


def test_clean_clone_still_fails_when_the_working_tree_fails_too(repo: Repo) -> None:
    repo.write("justfile", "check:\n\tfalse\n")
    repo.commit()
    repo.write("notes.txt", "x")
    assert _verdict(repo, "gate.clean-clone", audit=True)[0] is Verdict.FAILING


def test_clean_clone_evidence_is_the_cause_not_the_runners_own_trailer(repo: Repo) -> None:
    # a2kay: the runner's "recipe `check` failed" trailer said nothing; the cause was the line printed before it.
    repo.write("justfile", "check:\n\t@echo 'cannot read missing-config.toml' >&2\n\t@exit 3\n")
    repo.commit()
    verdict, evidence = _verdict(repo, "gate.clean-clone", audit=True)
    assert verdict is Verdict.FAILING
    assert "missing-config.toml" in evidence
    assert "recipe `check` failed" not in evidence


def test_clean_clone_evidence_names_the_command_that_failed(repo: Repo) -> None:
    repo.write("justfile", "check:\n\t@echo compiling\n\t@echo 'lint: 3 errors' >&2; exit 1\n")
    repo.commit()
    assert "lint: 3 errors" in _verdict(repo, "gate.clean-clone", audit=True)[1]


_HOOKS_OVERRIDE = (
    '[[override]]\nid = "gate.hooks-recipe"\ncode = "not-applicable"\nreason = "the owner installs hooks by hand on each machine"\n'
    'adr = "0003"\n'
)


def _owner_hooks_shaped(repo: Repo) -> None:
    """A repo with a settled decision: a gate, no hook config."""
    repo.write("justfile", "check:\n\ttrue\n")


def test_a_decided_gap_is_judged_as_before_without_an_override(repo: Repo) -> None:
    _owner_hooks_shaped(repo)
    assert _verdict(repo, "gate.hooks-recipe")[0] is Verdict.NOT_SET_UP


def test_a_settled_decision_is_an_adr_backed_override_that_never_expires(repo: Repo) -> None:
    _owner_hooks_shaped(repo)
    repo.write("docs/blueprint/blueprint.toml", _HOOKS_OVERRIDE)
    result = run(repo.root, concern="gate", env=repo.env, today=date(2099, 1, 1))
    rows = {r.id: r for r in result.rows}
    assert rows["gate.hooks-recipe"].verdict is Verdict.PASSING
    assert "ADR 0003" in rows["gate.hooks-recipe"].evidence
    assert result.problems == ()


def test_the_default_branch_must_be_main(repo: Repo) -> None:
    repo.write("a", "x")
    repo.commit()
    assert _verdict(repo, "gate.default-branch")[0] is Verdict.PASSING
    repo.git("branch", "-m", "main", "master")
    verdict, evidence = _verdict(repo, "gate.default-branch")
    assert verdict is Verdict.FAILING
    assert "master" in evidence


def test_a_repo_with_no_remote_is_not_set_up_and_one_with_origin_passes(repo: Repo) -> None:
    assert _verdict(repo, "gate.git-remote")[0] is Verdict.NOT_SET_UP
    repo.git("remote", "add", "upstream", "https://example.invalid/x.git")
    verdict, evidence = _verdict(repo, "gate.git-remote")
    assert verdict is Verdict.FAILING
    assert "upstream" in evidence
    repo.git("remote", "rename", "upstream", "origin")
    assert _verdict(repo, "gate.git-remote")[0] is Verdict.PASSING


def test_remote_and_branch_are_left_out_of_the_gate_run(repo: Repo) -> None:
    ids = {r.id for r in run(repo.root, concern="gate", env=repo.env).rows}
    assert not ids & {"gate.default-branch", "gate.git-remote"}


def _remote_branch(repo: Repo, name: str, files: dict[str, str]) -> None:
    """A remote-tracking `origin/<name>` one commit ahead of main holding `files`; main keeps `origin/main` at its tip."""
    repo.write("README", name)
    repo.commit()
    repo.git("update-ref", "refs/remotes/origin/main", "main")
    repo.git("checkout", "-q", "-b", "scratch")
    for rel, text in files.items():
        repo.write(rel, text)
    repo.commit()
    repo.git("update-ref", f"refs/remotes/origin/{name}", "scratch")
    repo.git("checkout", "-q", "main")
    repo.git("branch", "-q", "-D", "scratch")


def test_a_gate_row_names_a_remote_branch_ahead_that_holds_gate_files(repo: Repo) -> None:
    _remote_branch(repo, "wip/bootstrap", {"justfile": "check:\n\ttrue\n", "lefthook.yml": "x: 1\n", "src/a.py": ""})
    rows = {r.id: r for r in run_audit(repo.root, concern="gate", env=repo.env).rows}
    for check_id in ("gate.one-command", "gate.hooks-recipe"):
        row = rows[check_id]
        assert row.verdict is Verdict.NOT_SET_UP
        assert "origin/wip/bootstrap" in row.evidence
        assert "justfile" in row.evidence
        assert "lefthook.yml" in row.evidence
        assert "src/a.py" not in row.evidence
        assert "merge that branch or remediate on main" in row.remediation
        assert row.fixed_by is FixedBy.OWNER


def test_a_passing_gate_row_and_a_branch_with_no_gate_files_are_left_alone(repo: Repo) -> None:
    _remote_branch(repo, "feature", {"src/a.py": ""})
    row = {r.id: r for r in run_audit(repo.root, concern="gate", env=repo.env).rows}["gate.one-command"]
    assert "origin/feature" not in row.evidence
    assert "merge that branch" not in row.remediation
    repo.write("justfile", "check:\n\t@true\n")
    repo.commit()
    repo.git("update-ref", "refs/remotes/origin/main", "main")
    _remote_branch(repo, "wip/gate", {"justfile": "check:\n\ttrue\n"})
    rows = {r.id: r for r in run_audit(repo.root, concern="gate", env=repo.env).rows}
    assert rows["gate.one-command"].verdict is Verdict.PASSING
    assert "wip/gate" not in rows["gate.one-command"].evidence


def test_a_branch_already_merged_into_main_is_not_flagged(repo: Repo) -> None:
    repo.write("README", "x")
    repo.commit()
    repo.git("update-ref", "refs/remotes/origin/main", "main")
    repo.write("justfile", "check:\n\ttrue\n")
    repo.commit()
    repo.git("update-ref", "refs/remotes/origin/old", "main")
    repo.git("update-ref", "refs/remotes/origin/main", "main")
    row = {r.id: r for r in run_audit(repo.root, concern="gate", env=repo.env).rows}["gate.hooks-recipe"]
    assert "origin/old" not in row.evidence


def test_the_branch_note_is_audit_only(repo: Repo) -> None:
    _remote_branch(repo, "wip/bootstrap", {"justfile": "check:\n\ttrue\n"})
    row = {r.id: r for r in run(repo.root, concern="gate", env=repo.env).rows}["gate.one-command"]
    assert "wip/bootstrap" not in row.evidence


_HOMELAB_HOOKS = """repos:
  - repo: local
    hooks:
      - id: doctor
        entry: uv run tools/doctor.py
        language: system
      - id: lock-age
        entry: uv run tools/check-lock-age.py
        language: system
      - id: repo-tests
        entry: bash -c 'for t in tools/tests/test_*.py; do uv run "$t"; done'
        language: system
"""


def _homelab_shaped(repo: Repo) -> None:
    """`make check` runs no script itself: it runs pre-commit, whose local hooks run the repo's guards."""
    repo.write("justfile", "check: lint\nlint:\n\tuvx pre-commit run --all-files\n")
    repo.write(".pre-commit-config.yaml", _HOMELAB_HOOKS)
    repo.write("tools/doctor.py", "")
    repo.write("tools/check-lock-age.py", "")
    repo.write("tools/tests/test_doctor.py", "# plants a violation and runs tools/doctor.py\n")


def test_guards_run_through_pre_commit_hooks_are_judged_for_a_naming_test(repo: Repo) -> None:
    _homelab_shaped(repo)
    verdict, evidence = _verdict(repo, "gate.guards-have-red-tests")
    assert verdict is Verdict.FAILING
    assert "tools/check-lock-age.py" in evidence
    assert "tools/doctor.py" not in evidence
    repo.write("tools/tests/test_check_lock_age.py", "# plants a stale lock and runs check-lock-age\n")
    verdict, evidence = _verdict(repo, "gate.guards-have-red-tests")
    assert verdict is Verdict.PASSING
    assert "tools/doctor.py" in evidence
    assert "tools/tests/test_doctor.py" not in evidence


def test_hook_scripts_are_not_followed_when_the_gate_never_runs_the_hooks(repo: Repo) -> None:
    _homelab_shaped(repo)
    repo.write("justfile", "check:\n\ttrue\n")
    assert _verdict(repo, "gate.guards-have-red-tests")[0] is Verdict.NOT_APPLICABLE


def test_a_just_variable_in_the_recipe_is_expanded_before_scripts_are_found(repo: Repo) -> None:
    repo.write("justfile", "PY := 'uv run python'\ncheck:\n\t{{PY}} tools/check_design.py\n")
    repo.write("tools/check_design.py", "")
    verdict, evidence = _verdict(repo, "gate.guards-have-red-tests")
    assert verdict is Verdict.FAILING
    assert "tools/check_design.py" in evidence


def test_a_checker_script_the_gate_never_runs_is_flagged(repo: Repo) -> None:
    repo.write("justfile", "check:\n\tpython3 tools/check_text.py\n")
    repo.write("tools/check_text.py", "")
    repo.write("tools/check_design.py", "")
    repo.write("scripts/lint-docs.sh", "")
    repo.write("tools/tests/check_helpers.py", "")
    verdict, evidence = _verdict(repo, "gate.checkers-wired")
    assert verdict is Verdict.FAILING
    assert "tools/check_design.py" in evidence
    assert "scripts/lint-docs.sh" in evidence
    assert "check_text" not in evidence
    assert "check_helpers" not in evidence


def test_checker_scripts_run_by_the_gate_or_its_hooks_pass(repo: Repo) -> None:
    repo.write("justfile", "check:\n\tpython3 tools/check_text.py\n\tprek run --all-files\n")
    repo.write(
        ".pre-commit-config.yaml", "repos:\n  - repo: local\n    hooks:\n      - id: d\n        entry: uv run tools/check_design.py\n"
    )
    repo.write("tools/check_text.py", "")
    repo.write("tools/check_design.py", "")
    assert _verdict(repo, "gate.checkers-wired")[0] is Verdict.PASSING


def test_no_checker_scripts_means_the_check_does_not_apply(repo: Repo) -> None:
    repo.write("justfile", "check:\n\ttrue\n")
    assert _verdict(repo, "gate.checkers-wired")[0] is Verdict.NOT_APPLICABLE


def test_the_hooks_fix_merges_into_an_existing_config_and_never_overwrites_it(repo: Repo) -> None:
    # homelab (shelf-3gl): ~20 hooks of its own, and the fix said `blueprint recipe hooks > .pre-commit-config.yaml`.
    repo.write(".beads/config.yaml", "")
    repo.write(".pre-commit-config.yaml", "repos:\n- repo: local\n  hooks:\n  - id: doctor\n    entry: uv run tools/doctor.py\n")
    repo.write("justfile", "check: lint\nlint:\n\tuvx pre-commit run --all-files\n")
    row = next(r for r in run(repo.root, concern="gate", env=repo.env).rows if r.id == "gate.hooks-recipe")
    assert row.verdict is Verdict.FAILING
    assert "> .pre-commit-config.yaml" not in row.remediation
    assert "keep every hook" in row.remediation
    # the recipe's gate hook is pre-push only: a gate that runs `pre-commit run` does not recurse through it
    assert "leave out" not in row.remediation


def _recording_tool(repo: Repo, name: str) -> None:
    """A fake tool that appends its arguments to calls.log and succeeds."""
    log = repo.bin_dir / "calls.log"
    (repo.bin_dir / name).write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\nexit 0\n')
    (repo.bin_dir / name).chmod(0o755)


def test_clean_clone_runs_the_fresh_clone_steps_before_the_gate(repo: Repo) -> None:
    # a2kay (shelf-45k, shelf-8q7): an untrusted mise.toml and a clone with no bd database failed every fresh clone.
    repo.write("justfile", "check:\n\ttrue\n")
    repo.write("mise.toml", '[tools]\nprek = "0.5.5"\n')
    repo.write(".beads/config.yaml", "")
    repo.write("docs/blueprint/blueprint.toml", "[settings]\nclean-clone-seconds = 60\n")
    repo.commit()
    _recording_tool(repo, "mise")
    _recording_tool(repo, "bd")
    assert _verdict(repo, "gate.clean-clone", audit=True)[0] is Verdict.PASSING
    calls = (repo.bin_dir / "calls.log").read_text().splitlines()
    assert calls[:3] == ["mise trust --yes .", "mise install --locked", "bd bootstrap --yes"]


def test_clean_clone_ignores_the_injected_homes_mise_config(repo: Repo) -> None:
    repo.write("justfile", "check:\n\ttrue\n")
    repo.write("mise.toml", '[tools]\nprek = "0.5.5"\n')
    repo.write("docs/blueprint/blueprint.toml", "[settings]\nclean-clone-seconds = 60\n")
    repo.commit()
    seen = repo.bin_dir / "seen.log"
    (repo.bin_dir / "mise").write_text(f'#!/bin/sh\necho "$MISE_IGNORED_CONFIG_PATHS" >> "{seen}"\nexit 0\n')
    (repo.bin_dir / "mise").chmod(0o755)
    repo.env["HOME"] = "/injected/home"
    assert _verdict(repo, "gate.clean-clone", audit=True)[0] is Verdict.PASSING
    assert set(seen.read_text().split()) == {"/injected/home/.config/mise"}


def test_clean_clone_names_a_fresh_clone_step_that_failed(repo: Repo) -> None:
    repo.write("justfile", "check:\n\ttrue\n")
    repo.write(".beads/config.yaml", "")
    repo.commit()
    repo.fake_tool(repo.bin_dir / "bd", "Error: no remote")
    (repo.bin_dir / "bd").write_text("#!/bin/sh\necho 'Error: no remote' >&2\nexit 1\n")
    verdict, evidence = _verdict(repo, "gate.clean-clone", audit=True)
    assert verdict is Verdict.FAILING
    assert "bd bootstrap" in evidence


def test_clean_clone_retries_bd_bootstrap_over_the_other_transport(repo: Repo) -> None:
    # a2kay: its committed remote is https, the devbox has only an SSH key; CI is the reverse.
    repo.write("justfile", "check:\n\ttrue\n")
    repo.write(".beads/config.yaml", "")
    repo.write("docs/blueprint/blueprint.toml", "[settings]\nclean-clone-seconds = 60\n")
    repo.commit()
    (repo.bin_dir / "bd").write_text('#!/bin/sh\n[ -n "$GIT_CONFIG_COUNT" ] && exit 0\necho "Error: auth" >&2; exit 1\n')
    (repo.bin_dir / "bd").chmod(0o755)
    assert _verdict(repo, "gate.clean-clone", audit=True)[0] is Verdict.PASSING


def test_the_untested_script_fix_tells_a_guard_from_a_helper(repo: Repo) -> None:
    # a2kay (shelf-i6k): scripts/container_slot.py is a job queue, and the fix asked it to "plant the violation it guards".
    repo.write("justfile", "check:\n    python3 scripts/container_slot.py\n")
    repo.write("scripts/container_slot.py", "print('slot')\n")
    row = next(r for r in run(repo.root, concern="gate", env=repo.env).rows if r.id == "gate.guards-have-red-tests")
    assert row.verdict is Verdict.FAILING
    assert "for a helper" in row.remediation


# 2026-10-12: the shelf's own hook config ran no gate on pre-push, so a red typecheck reached main.
def test_a_config_whose_pre_push_runs_no_gate_fails(repo: Repo) -> None:
    gate_hook = _recipe()[_recipe().index("  - id: gate") :]
    repo.write(".pre-commit-config.yaml", _recipe().replace(gate_hook, ""))
    verdict, evidence = _verdict(repo, "gate.hooks-recipe")
    assert verdict is Verdict.FAILING
    assert "pre-push" in evidence


# a2kay, 2026-10-12: `python3 -I tools/check_dockerfile_pins.py` was not seen as a gate script at all.
def _pins_recipe() -> str:
    return (RECIPES / "check_dockerfile_pins.py").read_text()


def test_an_interpreter_flag_does_not_hide_a_gate_script(repo: Repo) -> None:
    repo.write("justfile", "check: images\nimages:\n\tpython3 -I tools/own_guard.py\n")
    repo.write("tools/own_guard.py", "")
    verdict, evidence = _verdict(repo, "gate.guards-have-red-tests")
    assert verdict is Verdict.FAILING
    assert "tools/own_guard.py" in evidence


def test_an_unchanged_blueprint_recipe_counts_as_tested_in_the_shelf(repo: Repo) -> None:
    repo.write("justfile", "check: images\nimages:\n\tpython3 -I tools/check_dockerfile_pins.py\n")
    repo.write("tools/check_dockerfile_pins.py", _pins_recipe())
    verdict, evidence = _verdict(repo, "gate.guards-have-red-tests")
    assert verdict is Verdict.PASSING
    assert "blueprint recipe" in evidence


def test_an_edited_copy_of_a_recipe_needs_its_own_test(repo: Repo) -> None:
    repo.write("justfile", "check: images\nimages:\n\tpython3 -I tools/check_dockerfile_pins.py\n")
    repo.write("tools/check_dockerfile_pins.py", _pins_recipe() + "\n# local change\n")
    assert _verdict(repo, "gate.guards-have-red-tests")[0] is Verdict.FAILING


def test_clean_clone_does_not_count_a_dirty_submodule_as_uncommitted(repo: Repo, tmp_path: Path) -> None:
    # lifesim: Unity's import rewrote materials inside a licensed submodule; that is not this repo's uncommitted work.
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@example.invalid"], ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=vendor, check=True)
    (vendor / "mat.txt").write_text("a")
    subprocess.run(["git", "add", "."], cwd=vendor, check=True)
    subprocess.run(["git", "commit", "-qm", "v"], cwd=vendor, check=True)
    repo.git("-c", "protocol.file.allow=always", "submodule", "add", "-q", str(vendor), "third_party/uma")
    repo.write("justfile", "check:\n\ttest -f generated.txt\n")
    repo.commit()
    repo.write("third_party/uma/mat.txt", "rewritten by the import")
    repo.write("generated.txt", "only on this machine")
    evidence = _verdict(repo, "gate.clean-clone", audit=True)[1]
    assert "generated.txt" in evidence
    assert "third_party/uma" not in evidence


def test_clean_clone_is_not_failed_by_an_lfs_smudge_filter(repo: Repo, tmp_path: Path) -> None:
    # lifesim: git ran the git-lfs shim as the smudge filter during clone and it errored; the clone skips smudge.
    repo.fake_tool(repo.bin_dir / "git-lfs", "")
    (repo.bin_dir / "git-lfs").write_text(
        '#!/bin/sh\n[ "$1" = pull ] || [ "$1" = version ] && exit 0\n[ -n "$GIT_LFS_SKIP_SMUDGE" ] && cat && exit 0\nexit 1\n'
    )
    config = tmp_path / "gitconfig"
    config.write_text('[filter "lfs"]\n\tsmudge = git-lfs smudge -- %f\n\trequired = true\n')
    repo.env |= {"GIT_CONFIG_GLOBAL": str(config), "GIT_CONFIG_NOSYSTEM": "1"}
    repo.write(".gitattributes", "*.bin filter=lfs\n")
    repo.write("a.bin", "x")
    repo.write("docs/blueprint/blueprint.toml", "[settings]\nclean-clone-seconds = 60\n")
    repo.write("justfile", "check:\n\ttrue\n")
    repo.git("-c", "filter.lfs.clean=cat", "add", "-A")
    repo.git("-c", "filter.lfs.clean=cat", "commit", "-qm", "x")
    verdict, evidence = _verdict(repo, "gate.clean-clone", audit=True)
    assert verdict is Verdict.PASSING, evidence


def _git_config_row(repo: Repo) -> tuple[Verdict, str, str]:
    row = next(r for r in run_audit(repo.root, concern="gate", env=repo.env).rows if r.id == "gate.git-config-clean")
    return row.verdict, row.evidence, row.remediation


def test_a_clean_git_config_passes(repo: Repo) -> None:
    assert _git_config_row(repo)[0] is Verdict.PASSING


def test_a_stray_core_worktree_in_the_clone_config_fails_with_the_unset_command(repo: Repo, tmp_path: Path) -> None:
    # A leaked GIT_WORK_TREE once wrote core.worktree: git then ran against another tree (homelab, lifesim).
    repo.git("config", "--local", "core.worktree", str(tmp_path))
    verdict, evidence, fix = _git_config_row(repo)
    assert verdict is Verdict.FAILING
    assert "core.worktree" in evidence
    assert fix == "git config --unset core.worktree"


def test_core_bare_true_in_a_non_bare_clone_fails_with_the_fix(repo: Repo) -> None:
    repo.git("config", "--local", "core.bare", "true")
    verdict, evidence, fix = _git_config_row(repo)
    assert verdict is Verdict.FAILING
    assert "core.bare" in evidence
    assert fix == "git config core.bare false"


def _lfs_gate_repo(repo: Repo, lfs_script: str | None) -> None:
    if lfs_script is not None:
        (repo.bin_dir / "git-lfs").write_text(lfs_script)
        (repo.bin_dir / "git-lfs").chmod(0o755)
    repo.write(".gitattributes", "*.bin filter=lfs diff=lfs merge=lfs -text\n")
    repo.write("docs/blueprint/blueprint.toml", "[settings]\nclean-clone-seconds = 60\n")
    repo.write("justfile", "check:\n\ttrue\n")
    repo.commit()


def test_clean_clone_pulls_lfs_files_in_the_clone_before_the_gate(repo: Repo, tmp_path: Path) -> None:
    log = tmp_path / "pulled.txt"
    _lfs_gate_repo(repo, f'#!/bin/sh\necho "$@ skip=$GIT_LFS_SKIP_SMUDGE cwd=$PWD" >> {log}\nexit 0\n')
    assert _verdict(repo, "gate.clean-clone", audit=True)[0] is Verdict.PASSING
    assert "pull skip=1" in log.read_text()
    assert "blueprint-clone-" in log.read_text()


def test_clean_clone_is_not_checked_when_the_lfs_pull_fails(repo: Repo) -> None:
    _lfs_gate_repo(repo, "#!/bin/sh\n[ \"$1\" = pull ] && { echo 'batch response: 404' >&2; exit 2; }\nexit 0\n")
    verdict, evidence = _verdict(repo, "gate.clean-clone", audit=True)
    assert verdict is Verdict.NOT_CHECKED
    assert "git lfs pull" in evidence


def test_clean_clone_is_not_checked_when_an_lfs_repo_has_no_git_lfs(repo: Repo, tmp_path: Path) -> None:
    _lfs_gate_repo(repo, None)
    only_git = tmp_path / "only-git"
    only_git.mkdir()
    (only_git / "git").symlink_to(shutil.which("git") or "git")
    (only_git / "make").symlink_to(shutil.which("make") or "make")
    repo.env["PATH"] = str(only_git)
    verdict, evidence = _verdict(repo, "gate.clean-clone", audit=True)
    assert verdict is Verdict.NOT_CHECKED
    assert "git-lfs is not installed" in evidence


@pytest.mark.parametrize("configured,expected", [(None, 120), ("240.5", 240.5), ("1", 120)])
def test_git_timeout_reports_command_and_checkpoint(
    repo: Repo, monkeypatch: pytest.MonkeyPatch, configured: str | None, expected: float
) -> None:
    """lifesim-gfr.12: a loaded machine is not a missing repository."""
    repo.env.pop("BLUEPRINT_TIMEOUT", None)
    if configured is not None:
        repo.env["BLUEPRINT_TIMEOUT"] = configured

    cmd = "git"

    def slow_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        # Detection runs its own git calls before the caller's env is attached; the row under test is `git remote`.
        argv = cast("list[str]", args[0]) if args else []
        if argv and argv[-1] == "remote":
            assert kwargs["timeout"] == expected
        raise subprocess.TimeoutExpired(cmd, expected)

    monkeypatch.setattr(subprocess, "run", slow_run)
    result = run_audit(repo.root, concern="gate", env=repo.env)
    row = next(r for r in result.rows if r.id == "gate.git-remote")
    assert row.verdict is Verdict.NOT_CHECKED
    assert f"timed out after {expected:g}s running `git remote`" in row.evidence
    assert "BLUEPRINT_TIMEOUT" in row.evidence
    assert "not a git repository" not in row.evidence
    output = gate_report(result)
    assert "gate.git-remote" in output
    assert row.evidence in output


def test_non_repository_reports_missing_repository(tmp_path: Path) -> None:
    result = run_audit(tmp_path, concern="gate")
    row = next(r for r in result.rows if r.id == "gate.git-remote")
    assert row.verdict is Verdict.NOT_CHECKED
    assert row.evidence == "not a git repository"


def test_a_copied_gate_script_the_shelf_now_ships_as_a_package_is_flagged(repo: Repo) -> None:
    repo.write("justfile", "check:\n\ttrue\n")
    repo.write("tools/gate_state.py", "# a2kay's copy\n")
    repo.write("scripts/changed.py", "")
    repo.write("tools/check_images.py", "")  # the repo's own, not a retired shelf script
    verdict, evidence = _verdict(repo, "gate.superseded-scripts")
    assert verdict is Verdict.FAILING
    assert "tools/gate_state.py" in evidence
    assert "any_gate" in evidence
    assert "scripts/changed.py" in evidence
    assert "check_images" not in evidence


def test_a_repo_with_none_of_the_retired_scripts_passes(repo: Repo) -> None:
    repo.write("justfile", "check:\n\ttrue\n")
    repo.write("tools/check_images.py", "")
    assert _verdict(repo, "gate.superseded-scripts")[0] is Verdict.PASSING


def test_a_retired_script_kept_on_purpose_is_excused_by_a_scoped_override(repo: Repo) -> None:
    repo.write("justfile", "check:\n\ttrue\n")
    repo.write("tools/gate_state.py", "")
    repo.write(
        "docs/blueprint/blueprint.toml",
        '[[override]]\nid = "gate.superseded-scripts"\nscope = "tools/gate_state.py"\nreason = "x"\nexpires = 2099-01-01\n',
    )
    assert _verdict(repo, "gate.superseded-scripts")[0] is Verdict.PASSING


def test_clean_clone_names_the_failing_step_and_shows_its_log(repo: Repo) -> None:
    repo.write(
        "justfile",
        "check:\n"
        "    @echo '--- lint'\n"
        + "".join(f"    @echo 'line {n}'\n" for n in range(1, 31))
        + "    @echo 'gate: lint 1s ✗ -- total 1s'\n    @echo 'gate: failed: lint'\n    @exit 1\n",
    )
    repo.commit()
    verdict, evidence = _verdict(repo, "gate.clean-clone", audit=True)
    assert verdict is Verdict.FAILING
    assert "step lint" in evidence
    assert "--- lint" in evidence
    assert "line 1\n" in evidence
    assert "line 20" in evidence
    assert "line 21" not in evidence


def test_a_failing_clean_clone_is_not_mixed_with_unmerged_branches(repo: Repo) -> None:
    repo.write("justfile", "check:\n    @exit 1\n")
    repo.commit()
    repo.git("update-ref", "refs/remotes/origin/main", "HEAD")
    repo.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    repo.git("checkout", "-q", "-b", "feature")
    repo.write("justfile", "check:\n    @true\n")
    repo.commit()
    repo.git("update-ref", "refs/remotes/origin/feature", "HEAD")
    repo.git("checkout", "-q", "main")
    verdict, evidence = _verdict(repo, "gate.clean-clone", audit=True)
    assert verdict is Verdict.FAILING
    assert "unmerged remote branch" not in evidence
