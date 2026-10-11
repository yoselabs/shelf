"""The gate read from a justfile (ADR 0023): the graph comes from `just --dump --dump-format json`.

The Makefile cases in test_gate.py stay: a repo not yet migrated is still judged, and fails `gate.runner`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_SHA = "11d5960a326750d5838078e36cf38b85af677262"
_CI = (
    "name: check\non: [push]\npermissions:\n  contents: read\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n"
    f"      - uses: actions/checkout@{_SHA} # v4\n      - run: {{gate}}\n"
)


def _row(repo: Repo, check_id: str, *, audit: bool = True) -> tuple[Verdict, str]:
    rows = {r.id: r for r in run(repo.root, concern="gate", audit=audit, env=repo.env).rows}
    return rows[check_id].verdict, rows[check_id].evidence


def test_one_command_passes_when_just_dry_run_resolves(repo: Repo) -> None:
    repo.write("justfile", "check: lint\nlint:\n    true\n")
    verdict, evidence = _row(repo, "gate.one-command")
    assert verdict is Verdict.PASSING
    assert "just --dry-run check" in evidence


def test_one_command_fails_when_check_names_a_missing_recipe(repo: Repo) -> None:
    repo.write("justfile", "check: lint preset\nlint:\n    true\n")
    verdict, evidence = _row(repo, "gate.one-command")
    assert verdict is Verdict.FAILING
    assert "preset" in evidence


def test_one_command_is_not_set_up_when_the_justfile_has_no_check(repo: Repo) -> None:
    repo.write("justfile", "lint:\n    true\n")
    assert _row(repo, "gate.one-command")[0] is Verdict.NOT_SET_UP


def test_the_dry_run_executes_nothing(repo: Repo) -> None:
    repo.write("justfile", "check:\n    touch ran.txt\n")
    _row(repo, "gate.one-command")
    assert not (repo.root / "ran.txt").exists()


def test_a_justfile_passes_the_runner_row(repo: Repo) -> None:
    repo.write("justfile", "check:\n    true\n")
    assert _row(repo, "gate.runner")[0] is Verdict.PASSING


def test_a_makefile_only_repo_fails_the_runner_row_and_the_remediation_names_the_migration(repo: Repo) -> None:
    repo.write("Makefile", "check:\n\ttrue\n")
    verdict, evidence = _row(repo, "gate.runner")
    assert verdict is Verdict.FAILING
    assert "Makefile" in evidence
    rows = {r.id: r for r in run(repo.root, concern="gate", env=repo.env).rows}
    assert "justfile" in rows["gate.runner"].remediation
    assert "ADR 0023" in rows["gate.runner"].remediation


def test_a_makefile_only_repo_is_still_judged_by_the_other_rows(repo: Repo) -> None:
    repo.write("Makefile", "check: lint\nlint:\n\ttrue\n")
    assert _row(repo, "gate.one-command")[0] is Verdict.PASSING


def test_the_runner_row_does_not_apply_without_any_gate(repo: Repo) -> None:
    assert _row(repo, "gate.runner")[0] is Verdict.NOT_APPLICABLE


@pytest.mark.parametrize("gate", ["just check", "just check-all", "uv run just check-all", "uvx rust-just@1.58.0 check"])
def test_ci_accepts_a_just_gate(repo: Repo, gate: str) -> None:
    repo.write(".github/workflows/check.yml", _CI.format(gate=gate))
    assert _row(repo, "gate.ci")[0] is Verdict.PASSING


def test_ci_without_the_gate_word_names_the_missing_command(repo: Repo) -> None:
    repo.write(".github/workflows/check.yml", _CI.format(gate="pytest"))
    verdict, evidence = _row(repo, "gate.ci")
    assert verdict is Verdict.FAILING
    assert "no workflow runs the gate" in evidence


def test_a_manifest_rewrite_ahead_of_a_just_gate_fails(repo: Repo) -> None:
    text = _CI.format(gate="uv run just check").replace("      - run: uv run", "      - run: uv lock\n      - run: uv run")
    repo.write(".github/workflows/check.yml", text)
    assert _row(repo, "gate.ci-no-manifest-edit")[0] is Verdict.FAILING


_JUSTFILE_BLUEPRINT = """check: (gate "check-host")

[private]
gate target:
    #!/usr/bin/env bash
    just {{ target }}

check-host: blueprint

blueprint:
    python3 -m blueprint check --repo . --gate
"""


def test_runs_blueprint_follows_an_argument_edge(repo: Repo) -> None:
    # `check` reaches `blueprint` only through gate("check-host"): the argument names a recipe.
    repo.write("justfile", _JUSTFILE_BLUEPRINT)
    assert _row(repo, "gate.runs-blueprint")[0] is Verdict.PASSING


def test_runs_blueprint_fails_when_no_recipe_the_gate_reaches_runs_it(repo: Repo) -> None:
    repo.write("justfile", _JUSTFILE_BLUEPRINT.replace("check-host: blueprint", "check-host:\n    true"))
    assert _row(repo, "gate.runs-blueprint")[0] is Verdict.NOT_SET_UP


def test_guard_scripts_are_found_through_dependencies_and_resolved_variables(repo: Repo) -> None:
    repo.write(
        "justfile",
        'guard_py := "tools/no-secrets.py"\ncheck: guard\nguard:\n    python3 {{ guard_py }}\nother:\n    python3 tools/unreached.py\n',
    )
    repo.write("tools/no-secrets.py", "")
    repo.write("tools/unreached.py", "")
    verdict, evidence = _row(repo, "gate.guards-have-red-tests")
    assert verdict is Verdict.FAILING
    assert "tools/no-secrets.py" in evidence
    assert "unreached" not in evidence
    repo.write("tests/test_no_secrets.py", "# plants a secret, runs no_secrets\n")
    assert _row(repo, "gate.guards-have-red-tests")[0] is Verdict.PASSING


def test_a_checker_script_nothing_runs_fails_and_one_the_gate_reaches_passes(repo: Repo) -> None:
    repo.write("justfile", "check: lint\nlint:\n    python3 tools/check_names.py\n")
    repo.write("tools/check_names.py", "")
    repo.write("tools/check_orphan.py", "")
    verdict, evidence = _row(repo, "gate.checkers-wired")
    assert verdict is Verdict.FAILING
    assert "check_orphan.py" in evidence
    assert "check_names.py" not in evidence


def test_the_gate_image_ignore_file_is_judged_for_a_justfile_gate(repo: Repo) -> None:
    repo.write("justfile", _JUSTFILE_BLUEPRINT + "image:\n    docker build -f tools/gate.Dockerfile -t gate .\n")
    repo.write(".beads/config.yaml", "")
    repo.write(".dockerignore", ".beads\n")
    repo.commit()
    verdict, evidence = _row(repo, "gate.runs-blueprint")
    assert verdict is Verdict.FAILING
    assert ".beads/config.yaml" in evidence


def test_clean_clone_runs_just_check(repo: Repo) -> None:
    repo.write("justfile", "check:\n    test -f committed.txt\n")
    repo.write("committed.txt", "x")
    repo.write("docs/blueprint/blueprint.toml", "[settings]\nclean-clone-seconds = 60\n")
    repo.commit()
    assert _row(repo, "gate.clean-clone")[0] is Verdict.PASSING
    repo.write("justfile", "check:\n    test -f uncommitted.txt\n")
    repo.commit()
    verdict, evidence = _row(repo, "gate.clean-clone")
    assert verdict is Verdict.FAILING
    assert "`just check`" in evidence


def test_a_justfile_without_just_installed_is_not_checked_not_failed(repo: Repo) -> None:
    repo.write("justfile", "check:\n    true\n")
    repo.env["PATH"] = str(repo.bin_dir)  # just (and everything else) off PATH
    rows = {r.id: r for r in run(repo.root, concern="gate", env=repo.env).rows}
    assert rows["gate.one-command"].verdict is Verdict.NOT_CHECKED


def test_the_pinned_just_in_the_repos_venv_is_used_when_none_is_on_path(repo: Repo) -> None:
    repo.write("justfile", "check:\n    true\n")
    repo.write(".venv/bin/just", "#!/bin/sh\nexit 0\n", executable=True)
    repo.env["PATH"] = str(repo.bin_dir)
    rows = {r.id: r for r in run(repo.root, concern="gate", env=repo.env).rows}
    assert rows["gate.one-command"].verdict is Verdict.PASSING
