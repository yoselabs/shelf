"""Stack rows judged from profile data; the survey template and its completeness check."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from blueprint import survey
from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_PYPROJECT = """[project]
name = "x"
requires-python = ">=3.12"

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["ALL"]
"""
_MAKEFILE = "check: lint\nlint:\n\tuv lock --check\n\tuv run ruff format --check .\n\tuv run ruff check .\n"


def _rows(repo: Repo) -> dict[str, tuple[Verdict, str, bool]]:
    return {r.id: (r.verdict, r.evidence, r.blueprint_gap) for r in run(repo.root, concern="stack", env=repo.env).rows}


def _python_repo(repo: Repo) -> None:
    repo.write("pyproject.toml", _PYPROJECT)
    repo.write("uv.lock", "")
    repo.write("Makefile", _MAKEFILE)


def test_a_role_configured_and_run_by_the_gate_passes(repo: Repo) -> None:
    _python_repo(repo)
    rows = _rows(repo)
    assert rows["stack.python-uv.formatter"][0] is Verdict.PASSING
    assert rows["stack.python-uv.linter"][0] is Verdict.PASSING
    assert rows["stack.python-uv.toolchain"][0] is Verdict.PASSING


def test_a_gate_without_the_lock_check_fails_the_toolchain(repo: Repo) -> None:
    _python_repo(repo)
    repo.write("Makefile", _MAKEFILE.replace("\tuv lock --check\n", ""))
    verdict, evidence, _ = _rows(repo)["stack.python-uv.toolchain"]
    assert verdict is Verdict.FAILING
    assert "uv lock --check" in evidence


def test_a_role_configured_but_not_in_the_gate_fails(repo: Repo) -> None:
    _python_repo(repo)
    repo.write("Makefile", "check:\n\tuv run ruff check .\n")
    verdict, evidence, _ = _rows(repo)["stack.python-uv.formatter"]
    assert verdict is Verdict.FAILING
    assert "ruff format --check" in evidence


def test_a_role_with_no_config_is_not_set_up_and_says_what_to_install(repo: Repo) -> None:
    _python_repo(repo)
    run_ = run(repo.root, concern="stack", env=repo.env)
    types = next(r for r in run_.rows if r.id == "stack.python-uv.types")
    assert types.verdict is Verdict.NOT_SET_UP
    assert "pyrefly" in types.remediation


def test_the_profile_row_lists_the_expected_toolset(repo: Repo) -> None:
    _python_repo(repo)
    verdict, evidence, _ = _rows(repo)["stack.python-uv.profile"]
    assert verdict is Verdict.PASSING
    assert "formatter: ruff format" in evidence
    assert "types: pyrefly" in evidence


def test_a_stack_without_a_profile_is_a_blueprint_gap_not_a_repo_failure(repo: Repo) -> None:
    repo.write("go.mod", "module x\n")
    result = run(repo.root, concern="stack", env=repo.env)
    row = next(r for r in result.rows if r.id == "stack.go.profile")
    assert row.verdict is Verdict.NOT_CHECKED
    assert row.blueprint_gap
    assert "no standard for go" in row.evidence
    assert "profiles/go.toml" in row.remediation
    assert result.exit_code == 0


def test_an_untested_role_is_a_blueprint_gap(repo: Repo) -> None:
    _python_repo(repo)
    verdict, evidence, gap = _rows(repo)["stack.python-uv.architecture"]
    assert verdict is Verdict.NOT_CHECKED
    assert gap
    assert "no standard yet" in evidence


def test_check_all_counts_as_the_gate(repo: Repo) -> None:
    _python_repo(repo)
    repo.write("Makefile", _MAKEFILE + "check-all: lint cov\ncov:\n\tuv run pytest --cov-fail-under=80\n")
    assert _rows(repo)["stack.python-uv.coverage"][0] is Verdict.PASSING


def _gate_with_cov(repo: Repo, recipe: str, *, pyproject: str = _PYPROJECT) -> None:
    _python_repo(repo)
    repo.write("pyproject.toml", pyproject)
    repo.write("Makefile", f"check: lint cov\n{_MAKEFILE.split(chr(10), 1)[1]}cov:\n\t{recipe}\n")


@pytest.mark.parametrize(
    "recipe",
    [
        "coverage run -m pytest -p no:cov && coverage report --fail-under=90",
        "coverage run -m pytest && coverage report -m --fail-under 90",
    ],
)
def test_coverage_py_floor_on_the_command_line_counts_as_a_floor(repo: Repo, recipe: str) -> None:
    # a2kay: pytest-cov breaks duckdb's lazy C-extension import, so the floor is coverage.py's own.
    _gate_with_cov(repo, recipe)
    assert _rows(repo)["stack.python-uv.coverage"][0] is Verdict.PASSING


def test_coverage_py_floor_in_pyproject_counts_when_the_gate_reports(repo: Repo) -> None:
    _gate_with_cov(repo, "coverage run -m pytest && coverage report", pyproject=_PYPROJECT + "\n[tool.coverage.report]\nfail_under = 90\n")
    assert _rows(repo)["stack.python-uv.coverage"][0] is Verdict.PASSING


@pytest.mark.parametrize(
    ("recipe", "pyproject"),
    [
        ("coverage run -m pytest && coverage report", _PYPROJECT),
        # a floor in pyproject is never read when the gate only measures and never reports
        ("coverage run -m pytest", _PYPROJECT + "\n[tool.coverage.report]\nfail_under = 90\n"),
    ],
)
def test_coverage_with_no_enforced_floor_still_fails(repo: Repo, recipe: str, pyproject: str) -> None:
    _gate_with_cov(repo, recipe, pyproject=pyproject)
    verdict, evidence, _ = _rows(repo)["stack.python-uv.coverage"]
    assert verdict is Verdict.FAILING
    assert "fail-under" in evidence


def test_the_survey_template_has_every_question_and_an_empty_one_is_incomplete() -> None:
    text = survey.template("x", "abc")
    questions, _, _ = survey.load()
    assert all(f"| {q.id} |" in text for q in questions)
    assert len(survey.problems(text)) == len(questions)


def test_a_filled_survey_is_complete_and_a_bare_no_is_not() -> None:
    questions, _, _ = survey.load()
    filled = "\n".join(f"| {q.id} | q | yes |  |" for q in questions)
    assert survey.problems(filled) == []
    bad = filled.replace(f"| {questions[0].id} | q | yes |  |", f"| {questions[0].id} | q | no |  |")
    assert survey.problems(bad) == [f"{questions[0].id}: 'no' needs evidence"]
