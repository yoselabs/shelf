"""Gate checkpoints: each seen passing on a sound repo and failing on a planted violation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_SHA = "11d5960a326750d5838078e36cf38b85af677262"
_SOUND_CI = f"""name: check
on: [push]
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{_SHA} # v4
      - run: make check
"""


def _verdict(repo: Repo, check_id: str, *, audit: bool = True) -> tuple[Verdict, str]:
    rows = {r.id: r for r in run(repo.root, concern="gate", audit=audit, env=repo.env).rows}
    return rows[check_id].verdict, rows[check_id].evidence


def test_one_command_passes_when_check_resolves(repo: Repo) -> None:
    repo.write("Makefile", "check: lint\nlint:\n\ttrue\n")
    assert _verdict(repo, "gate.one-command")[0] is Verdict.PASSING


def test_one_command_is_not_set_up_without_a_makefile(repo: Repo) -> None:
    assert _verdict(repo, "gate.one-command")[0] is Verdict.NOT_SET_UP


def test_one_command_fails_when_check_names_a_missing_target(repo: Repo) -> None:
    repo.write("Makefile", "check: lint preset\nlint:\n\ttrue\n")
    verdict, evidence = _verdict(repo, "gate.one-command")
    assert verdict is Verdict.FAILING
    assert "preset" in evidence


def test_ci_passes_when_pinned_and_running_the_gate(repo: Repo) -> None:
    repo.write(".github/workflows/check.yml", _SOUND_CI)
    assert _verdict(repo, "gate.ci")[0] is Verdict.PASSING


def test_ci_fails_on_a_tag_pinned_action(repo: Repo) -> None:
    repo.write(".github/workflows/check.yml", _SOUND_CI.replace(f"@{_SHA} # v4", "@v4"))
    verdict, evidence = _verdict(repo, "gate.ci")
    assert verdict is Verdict.FAILING
    assert "actions/checkout@v4" in evidence


def test_ci_fails_without_permissions_or_the_gate_word(repo: Repo) -> None:
    repo.write(".github/workflows/check.yml", _SOUND_CI.replace("permissions:\n  contents: read\n", "").replace("make check", "pytest"))
    verdict, evidence = _verdict(repo, "gate.ci")
    assert verdict is Verdict.FAILING
    assert "permissions" in evidence
    assert "no workflow runs `make check`" in evidence


def test_ci_is_not_set_up_without_workflows(repo: Repo) -> None:
    assert _verdict(repo, "gate.ci")[0] is Verdict.NOT_SET_UP


def test_hooks_pass_with_one_executable_pre_commit(repo: Repo) -> None:
    repo.write(".git/hooks/pre-commit", "#!/bin/sh\nmake lint\n", executable=True)
    assert _verdict(repo, "gate.one-hook-manager")[0] is Verdict.PASSING


def test_hooks_fail_with_two_managers(repo: Repo) -> None:
    repo.write(".pre-commit-config.yaml", "repos: []\n")
    repo.write("lefthook.yml", "pre-commit: {}\n")
    verdict, evidence = _verdict(repo, "gate.one-hook-manager")
    assert verdict is Verdict.FAILING
    assert "pre-commit, lefthook" in evidence


def test_hooks_fail_when_beads_is_not_chained(repo: Repo) -> None:
    repo.write(".beads/config.yaml", "")
    repo.write(".git/hooks/pre-commit", "#!/bin/sh\nmake lint\n", executable=True)
    assert _verdict(repo, "gate.one-hook-manager")[0] is Verdict.FAILING


def test_hooks_are_not_set_up_without_a_pre_commit(repo: Repo) -> None:
    assert _verdict(repo, "gate.one-hook-manager")[0] is Verdict.NOT_SET_UP


def test_guard_scripts_pass_when_a_test_names_each(repo: Repo) -> None:
    repo.write("Makefile", "check: guard\nguard:\n\tpython3 tools/no-secrets.py\n")
    repo.write("tools/no-secrets.py", "")
    repo.write("tests/test_no_secrets.py", "# runs tools/no_secrets against a planted secret\n")
    assert _verdict(repo, "gate.guards-have-red-tests")[0] is Verdict.PASSING


def test_guard_scripts_fail_when_one_has_no_test(repo: Repo) -> None:
    repo.write(
        "Makefile", "check: guard\nguard:\n\t@g=tools/no-secrets.py; python3 $$g\nother:\n\tpython3 tools/untested-but-unreached.py\n"
    )
    repo.write("tools/no-secrets.py", "")
    repo.write("tools/untested-but-unreached.py", "")
    verdict, evidence = _verdict(repo, "gate.guards-have-red-tests")
    assert verdict is Verdict.FAILING
    assert "tools/no-secrets.py" in evidence
    assert "unreached" not in evidence


def test_guard_scripts_do_not_apply_when_check_runs_none(repo: Repo) -> None:
    repo.write("Makefile", "check:\n\ttrue\n")
    assert _verdict(repo, "gate.guards-have-red-tests")[0] is Verdict.NOT_APPLICABLE


def test_clean_clone_is_audit_only_and_left_out_of_the_gate_run(repo: Repo) -> None:
    rows = run(repo.root, concern="gate", env=repo.env).rows
    assert "gate.clean-clone" not in {r.id for r in rows}


def test_clean_clone_passes_within_its_budget(repo: Repo) -> None:
    repo.write("Makefile", "check:\n\ttrue\n")
    repo.write("docs/blueprint/blueprint.toml", "[settings]\nclean-clone-seconds = 60\n")
    repo.commit()
    assert _verdict(repo, "gate.clean-clone", audit=True)[0] is Verdict.PASSING


def test_clean_clone_fails_when_an_uncommitted_file_is_what_made_it_pass(repo: Repo) -> None:
    repo.write("Makefile", "check:\n\ttest -f generated.txt\n")
    repo.commit()
    repo.write("generated.txt", "only on this machine")
    verdict, evidence = _verdict(repo, "gate.clean-clone", audit=True)
    assert verdict is Verdict.FAILING
    assert "fresh clone" in evidence
