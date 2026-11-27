"""The gate read from a justfile (ADR 0023): the graph comes from `just --dump --dump-format json`.

A Makefile is never read as a gate; a repo with one and no justfile fails `gate.runner`.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest
from blueprint import gate_graph
from blueprint.model import Context, Profile, Verdict
from blueprint.runner import run, run_audit

if TYPE_CHECKING:
    from blueprint.testing import Repo


def _row(repo: Repo, check_id: str, *, audit: bool = True) -> tuple[Verdict, str]:
    rows = {r.id: r for r in (run_audit if audit else run)(repo.root, concern="gate", env=repo.env).rows}
    return rows[check_id].verdict, rows[check_id].evidence


def test_one_command_passes_when_just_dry_run_resolves(repo: Repo) -> None:
    repo.write("justfile", "check: lint\nlint:\n    true\n")
    verdict, evidence = _row(repo, "gate.one-command")
    assert verdict is Verdict.PASSING
    assert "just --dry-run check" in evidence


def test_gate_graph_needs_no_release_recipe(repo: Repo) -> None:
    repo.write("justfile", "check: test\ntest:\n    uv run blueprint gate test\nunused:\n    uv run blueprint gate test-all\n")
    gate = gate_graph.load(Context(repo.root, Profile("library", (), (), (), None), env=repo.env))
    assert gate is not None
    assert not gate.has_recipe("check-all")
    assert "blueprint gate test" in gate.gate_recipes()
    assert "test-all" not in gate.gate_recipes()


def test_the_justfile_is_dumped_once_per_run_however_many_checks_ask(repo: Repo) -> None:
    repo.write("justfile", "check:\n    true\n")
    counter = repo.bin_dir / "dumps"
    real = shutil.which("just", path=repo.env["PATH"])
    assert real is not None
    (repo.bin_dir / "just").write_text(f'#!/bin/sh\necho x >> "{counter}"\nexec "{real}" "$@"\n')
    (repo.bin_dir / "just").chmod(0o755)
    ctx = Context(repo.root, Profile("library", (), (), (), None), env=repo.env)
    first, second = gate_graph.load(ctx), gate_graph.load(ctx)
    assert first is second
    assert counter.read_text().count("x") == 1


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


@pytest.mark.parametrize("value", ["-p no:cov --maxfail=1", "--maxfail=1"])
def test_recipe_calls_preserves_quoted_flag_values(repo: Repo, value: str) -> None:
    repo.write("justfile", f'check:\n    uv run blueprint gate test --pytest-args "{value}"\n')
    assert _row(repo, "gate.recipe-calls", audit=False)[0] is Verdict.PASSING


def test_recipe_calls_checks_continued_lines(repo: Repo) -> None:
    repo.write("justfile", "check:\n    uv run blueprint gate test \\\n        --bogus\n")
    verdict, evidence = _row(repo, "gate.recipe-calls", audit=False)
    assert verdict is Verdict.FAILING
    assert "--bogus" in evidence


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


def test_a_makefile_is_not_read_as_a_gate(repo: Repo) -> None:
    # shelf-rofp: ADR 0023 and 0028, no backward compatibility; the runner row says why.
    repo.write("Makefile", "check: lint\nlint:\n\ttrue\n")
    assert _row(repo, "gate.one-command")[0] is Verdict.NOT_SET_UP


def test_the_runner_row_does_not_apply_without_any_gate(repo: Repo) -> None:
    assert _row(repo, "gate.runner")[0] is Verdict.NOT_APPLICABLE


_JUSTFILE_BLUEPRINT = """check: (gate "check-host")

[private]
gate target:
    #!/usr/bin/env bash
    just {{ target }}

check-host: blueprint

blueprint:
    python3 -m blueprint check --repo . --brief
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
    repo.write_executable(".venv/bin/just", "#!/bin/sh\nexit 0\n")
    repo.env["PATH"] = str(repo.bin_dir)
    rows = {r.id: r for r in run(repo.root, concern="gate", env=repo.env).rows}
    assert rows["gate.one-command"].verdict is Verdict.PASSING


def _fix(repo: Repo, check_id: str) -> str:
    return next(r.remediation for r in run(repo.root, concern="gate", env=repo.env).rows if r.id == check_id)


def test_a_repo_with_no_code_that_declares_python_gets_the_onboarding_fix(repo: Repo) -> None:
    repo.write("docs/blueprint/blueprint.toml", '[profile]\nstacks = ["python-uv"]\n')
    assert "blueprint init" in _fix(repo, "gate.one-command")


def test_a_repo_with_no_stack_is_told_how_to_declare_one(repo: Repo) -> None:
    repo.write("README.md", "# idea\n")
    fix = _fix(repo, "gate.one-command")
    assert "stacks = [" in fix
    assert "docs/blueprint/blueprint.toml" in fix


def _runner_fix(repo: Repo) -> str:
    return next(r.remediation for r in run(repo.root, concern="gate", env=repo.env).rows if r.id == "gate.runner")


def test_the_runner_fix_in_a_python_repo_is_uv_add_rust_just(repo: Repo) -> None:
    repo.write("Makefile", "check:\n\ttrue\n")
    repo.write("pyproject.toml", '[project]\nname = "x"\nversion = "0"\n')
    fix = _runner_fix(repo)
    assert "uv add --dev rust-just" in fix
    assert "uv run just check" in fix


def test_the_runner_fix_without_a_pyproject_pins_just_in_mise(repo: Repo) -> None:
    # lifesim (Unity/.NET): no pyproject, so `uv add` has nothing to add to.
    repo.write("Makefile", "check:\n\ttrue\n")
    fix = _runner_fix(repo)
    assert "uv add" not in fix
    assert "uv run" not in fix
    assert 'just = "' in fix
    assert "mise.toml" in fix
    assert "ADR 0024" in fix


def test_gate_rows_keep_their_order_metadata_and_audit_selection(repo: Repo) -> None:
    # shelf-50w.1: domain ownership must not change the checkpoint contract.
    expected = (
        ("gate.one-command", 1, False),
        ("gate.runner", 1, False),
        ("gate.no-ci", 1, False),
        ("gate.step-inputs", 1, False),
        ("gate.narrowed-inputs-have-a-reason", 1, False),
        ("gate.wide-inputs-have-a-reason", 1, False),
        ("gate.hooks-recipe", 4, False),
        ("gate.hooks-installed", 3, True),
        ("gate.runs-blueprint", 2, False),
        ("gate.guards-have-red-tests", 2, False),
        ("gate.clean-clone", 1, True),
        ("gate.checkers-wired", 1, False),
        ("gate.superseded-scripts", 1, False),
        ("gate.default-branch", 1, True),
        ("gate.git-remote", 1, True),
        ("gate.lfs-binaries", 1, False),
        ("gate.git-config-clean", 1, True),
        ("gate.lfs-installed", 1, True),
        ("gate.recipe-calls", 1, False),
        ("gate.recipe-shadowing", 1, False),
    )
    audited = run_audit(repo.root, concern="gate", env=repo.env)
    gated = run(repo.root, concern="gate", env=repo.env)
    assert [(r.id, r.version) for r in audited.rows] == [(key, version) for key, version, _ in expected]
    assert [(r.id, r.version) for r in gated.rows] == [(key, version) for key, version, audit in expected if not audit]
    assert all(r.concern == "gate" and r.layer == "generic" for r in audited.rows)
    assert gated.skipped_audit == sum(audit for _, _, audit in expected)
    assert audited.set_hash == gated.set_hash
    assert not run_audit(repo.root, concern="gate_no_ci", env=repo.env).rows


_STEPS = 'check: (steps "lint" "test")\nsteps +names:\n    true\nlint:\n    true\ntest:\n    true\n'


def test_step_inputs_fails_with_no_declaration_file(repo: Repo) -> None:
    repo.write("justfile", _STEPS)
    verdict, evidence = _row(repo, "gate.step-inputs")
    assert verdict is Verdict.FAILING
    assert "lint, test" in evidence


def test_step_inputs_names_the_step_that_declares_nothing(repo: Repo) -> None:
    repo.write("justfile", _STEPS)
    repo.write("gate-inputs.toml", 'lint = ["*.py"]\n')
    verdict, evidence = _row(repo, "gate.step-inputs")
    assert verdict is Verdict.FAILING
    assert evidence.startswith("test:")


def test_step_inputs_passes_when_every_step_declares(repo: Repo) -> None:
    repo.write("justfile", _STEPS)
    repo.write("gate-inputs.toml", 'lint = ["*.py"]\ntest = ["*"]\n')
    assert _row(repo, "gate.step-inputs")[0] is Verdict.PASSING


def test_step_inputs_is_not_applicable_when_the_gate_runs_no_steps(repo: Repo) -> None:
    repo.write("justfile", "check: lint\nlint:\n    true\n")
    assert _row(repo, "gate.step-inputs")[0] is Verdict.NOT_APPLICABLE


def test_a_step_run_on_any_change_without_a_reason_fails_and_is_named(repo: Repo) -> None:
    repo.write("justfile", _STEPS)
    repo.write("gate-inputs.toml", 'lint = ["*.py"]\ntest = ["*"]\n')
    verdict, evidence = _row(repo, "gate.wide-inputs-have-a-reason")
    assert verdict is Verdict.FAILING
    assert "test" in evidence
    assert "lint" not in evidence


def test_a_wide_step_passes_with_a_reason_of_a_known_kind(repo: Repo) -> None:
    repo.write("justfile", _STEPS)
    repo.write("gate-inputs.toml", 'lint = ["*.py"]\ntest = ["*"]\n[wide]\ntest = "self-keyed: units hash what each reaches"\n')
    assert _row(repo, "gate.wide-inputs-have-a-reason")[0] is Verdict.PASSING


@pytest.mark.parametrize("reason", ["because", "self-keyed:", "reads everything: yes", ""])
def test_a_wide_reason_must_start_with_a_known_kind_and_say_something(repo: Repo, reason: str) -> None:
    repo.write("justfile", _STEPS)
    repo.write("gate-inputs.toml", f'lint = ["*.py"]\ntest = ["*"]\n[wide]\ntest = "{reason}"\n')
    assert _row(repo, "gate.wide-inputs-have-a-reason")[0] is Verdict.FAILING


def test_a_wide_entry_for_a_step_that_is_no_longer_wide_is_stale(repo: Repo) -> None:
    repo.write("justfile", _STEPS)
    repo.write("gate-inputs.toml", 'lint = ["*.py"]\ntest = ["*.py"]\n[wide]\ntest = "self-keyed: units"\n')
    verdict, evidence = _row(repo, "gate.wide-inputs-have-a-reason")
    assert verdict is Verdict.FAILING
    assert "test" in evidence


def test_the_wide_row_is_not_applicable_with_no_declarations(repo: Repo) -> None:
    repo.write("justfile", _STEPS)
    assert _row(repo, "gate.wide-inputs-have-a-reason")[0] is Verdict.NOT_APPLICABLE


_DEFAULTS = 'lint = ["*.py"]\ntest = ["*"]\n[wide]\ntest = "self-keyed: units"\n'
_MINE = 'check: (steps "lint" "test" "mine")\nsteps +names:\n    true\nlint:\n    true\ntest:\n    true\nmine:\n    true\n'


def test_a_repo_with_no_declaration_file_passes_on_the_rendered_defaults(repo: Repo) -> None:
    repo.write("justfile", _STEPS)
    repo.write(".blueprint/step-inputs.toml", _DEFAULTS)
    assert _row(repo, "gate.step-inputs")[0] is Verdict.PASSING


def test_a_step_with_no_default_and_no_declaration_fails_and_is_named(repo: Repo) -> None:
    repo.write("justfile", _MINE)
    repo.write(".blueprint/step-inputs.toml", _DEFAULTS)
    verdict, evidence = _row(repo, "gate.step-inputs")
    assert verdict is Verdict.FAILING
    assert evidence.startswith("mine:")


def test_the_defaults_wide_steps_need_no_reason_from_the_repo(repo: Repo) -> None:
    repo.write("justfile", _STEPS)
    repo.write(".blueprint/step-inputs.toml", _DEFAULTS)
    assert _row(repo, "gate.wide-inputs-have-a-reason")[0] is Verdict.NOT_APPLICABLE


def test_a_widening_list_needs_no_reason(repo: Repo) -> None:
    repo.write("justfile", _STEPS)
    repo.write(".blueprint/step-inputs.toml", _DEFAULTS)
    repo.write("gate-inputs.toml", 'lint = ["*.cfg"]\n')
    assert _row(repo, "gate.narrowed-inputs-have-a-reason")[0] is Verdict.NOT_APPLICABLE
    assert _row(repo, "gate.step-inputs")[0] is Verdict.PASSING


def test_narrowing_with_a_reason_passes(repo: Repo) -> None:
    repo.write("justfile", _STEPS)
    repo.write(".blueprint/step-inputs.toml", _DEFAULTS)
    repo.write("gate-inputs.toml", 'lint = ["src/*.py"]\n[narrow]\nlint = "only src is linted; scripts are shellchecked elsewhere"\n')
    assert _row(repo, "gate.narrowed-inputs-have-a-reason")[0] is Verdict.PASSING


@pytest.mark.parametrize("reason", ["", "because", "   "])
def test_narrowing_without_a_reason_fails(repo: Repo, reason: str) -> None:
    repo.write("justfile", _STEPS)
    repo.write(".blueprint/step-inputs.toml", _DEFAULTS)
    repo.write("gate-inputs.toml", f'lint = ["src/*.py"]\n[narrow]\nlint = "{reason}"\n')
    verdict, evidence = _row(repo, "gate.narrowed-inputs-have-a-reason")
    assert verdict is Verdict.FAILING
    assert "lint" in evidence


def test_a_narrow_entry_with_no_list_or_no_default_fails(repo: Repo) -> None:
    repo.write("justfile", _STEPS)
    repo.write(".blueprint/step-inputs.toml", _DEFAULTS)
    repo.write("gate-inputs.toml", 'mine = ["*.x"]\n[narrow]\nlint = "a long enough reason here"\nmine = "a long enough reason here"\n')
    verdict, evidence = _row(repo, "gate.narrowed-inputs-have-a-reason")
    assert verdict is Verdict.FAILING
    assert "no `lint = [...]` list" in evidence
    assert "no default to narrow" in evidence
