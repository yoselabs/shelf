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


def test_a_justfile_gate_is_read_through_its_graph_and_a_recipe_nothing_reaches_does_not_count(repo: Repo) -> None:
    _python_repo(repo)
    repo.write("Makefile", "")
    gate = 'check: (gate "lint")\n\n[private]\ngate target:\n    just {{ target }}\n\n'
    repo.write("justfile", gate + "lint:\n    uv lock --check\n    uv run ruff format --check .\n    uv run ruff check .\n")
    assert _rows(repo)["stack.python-uv.formatter"][0] is Verdict.PASSING
    repo.write("justfile", "check:\n    true\n\nlint:\n    uv run ruff format --check .\n    uv run ruff check .\n")
    assert _rows(repo)["stack.python-uv.formatter"][0] is Verdict.FAILING


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
    # Unity's embedded shader lint has no tested standard; framework rows share the stack rows' judging.
    repo.write("Game/ProjectSettings/ProjectVersion.txt", "m_EditorVersion: 6000.3.2f1\n")
    row = next(r for r in run(repo.root, concern="framework", env=repo.env).rows if r.id == "framework.unity.embedded-script-lint")
    assert row.verdict is Verdict.NOT_CHECKED
    assert row.blueprint_gap
    assert "no standard yet" in row.evidence


def test_the_architecture_role_wants_import_linter_configured_and_run_by_the_gate(repo: Repo) -> None:
    _python_repo(repo)
    verdict, evidence, _ = _rows(repo)["stack.python-uv.architecture"]
    assert verdict is Verdict.NOT_SET_UP
    assert "[tool.importlinter" in evidence
    repo.write("pyproject.toml", _PYPROJECT + '\n[tool.importlinter]\nroot_packages = ["x"]\n')
    assert _rows(repo)["stack.python-uv.architecture"][0] is Verdict.FAILING  # configured, not in the gate
    repo.write("Makefile", _MAKEFILE.replace("check: lint", "check: lint arch") + "arch:\n\tuv run lint-imports\n")
    assert _rows(repo)["stack.python-uv.architecture"][0] is Verdict.PASSING


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


def _dotnet_repo(repo: Repo, roll_forward: str = "latestPatch") -> None:
    repo.write(
        "global.json",
        f'{{"sdk": {{"version": "10.0.301", "rollForward": "{roll_forward}"}}, "test": {{"runner": "Microsoft.Testing.Platform"}}}}',
    )
    repo.write(
        "Directory.Build.props",
        "<Project><PropertyGroup><RestorePackagesWithLockFile>true</RestorePackagesWithLockFile></PropertyGroup></Project>",
    )
    repo.write("src/App/App.csproj", "<Project/>")


def _two_installs(repo: Repo, *, on_path: str, elsewhere: str) -> None:
    """Homebrew's dotnet on PATH, the official installer's in /usr/local/share/dotnet (the one Godot's editor resolves)."""
    repo.fake_tool(repo.bin_dir / "dotnet", f"{on_path} [/opt/homebrew/sdk]")
    repo.fake_tool(repo.sysroot / "usr/local/share/dotnet/dotnet", f"{elsewhere} [/usr/local/share/dotnet/sdk]")


def test_the_profile_row_names_the_file_that_set_the_stack(repo: Repo) -> None:
    _dotnet_repo(repo)
    assert "detected from src/App/App.csproj" in _rows(repo)["stack.dotnet.profile"][1]


def test_a_global_json_a_second_dotnet_install_cannot_satisfy_fails_naming_both(repo: Repo) -> None:
    # lifesim: pinned the PATH install's 10.0.301 latestPatch; Godot's editor used 10.0.401 and its build exited 155.
    _dotnet_repo(repo)
    _two_installs(repo, on_path="10.0.301", elsewhere="10.0.401")
    verdict, evidence, _ = _rows(repo)["stack.dotnet.toolchain"]
    assert verdict is Verdict.FAILING
    assert str(repo.bin_dir / "dotnet") in evidence
    assert "usr/local/share/dotnet/dotnet" in evidence
    assert "10.0.401" in evidence


@pytest.mark.parametrize(
    ("roll_forward", "on_path", "elsewhere"),
    [
        ("latestFeature", "10.0.301", "10.0.401"),  # the policy admits the newer feature band
        ("latestPatch", "10.0.301", "10.0.302"),  # same feature band, a newer patch
        ("latestPatch", "10.0.301", "10.0.301"),
    ],
)
def test_installs_that_each_carry_an_accepted_sdk_pass(repo: Repo, roll_forward: str, on_path: str, elsewhere: str) -> None:
    _dotnet_repo(repo, roll_forward)
    _two_installs(repo, on_path=on_path, elsewhere=elsewhere)
    assert _rows(repo)["stack.dotnet.toolchain"][0] is Verdict.PASSING


def test_the_one_install_there_is_must_satisfy_the_pin_too(repo: Repo) -> None:
    _dotnet_repo(repo, "disable")
    repo.fake_tool(repo.bin_dir / "dotnet", "10.0.302 [/opt/homebrew/sdk]")
    assert _rows(repo)["stack.dotnet.toolchain"][0] is Verdict.FAILING


def test_flake_nix_in_a_subfolder_detects_the_nix_stack(repo: Repo) -> None:
    # Host flakes in subfolders, none at the root.
    repo.write("hosts/bee/flake.nix", "{ }")
    repo.write("hosts/sol/flake.nix", "{ }")
    repo.write("hosts/bee/flake.lock", "{}")
    rows = _rows(repo)
    assert "detected from hosts/bee/flake.nix, hosts/sol/flake.nix" in rows["stack.nix.profile"][1]
    assert rows["stack.nix.coverage"][0] is Verdict.NOT_APPLICABLE
    assert rows["stack.nix.tests"][0] is Verdict.NOT_SET_UP  # the eval tier: tests/nix/*.nix


def test_many_compose_files_make_one_compose_table(repo: Repo) -> None:
    for name in ("web", "proxy", "media"):
        repo.write(f"stacks/{name}/compose.yml", "services: {}")
    rows = _rows(repo)
    assert [k for k in rows if k.endswith(".profile")] == ["stack.compose.profile"]
    assert "stacks/media/compose.yml" in rows["stack.compose.profile"][1]


def test_a_nix_host_eval_in_the_gate_passes_the_types_row(repo: Repo) -> None:
    repo.write("hosts/bee/flake.nix", "{ }")
    repo.write("tools/check-host.sh", "#!/bin/sh\n")
    repo.write("justfile", "check: check-host\ncheck-host:\n    bash tools/check-host.sh bee\n")
    assert _rows(repo)["stack.nix.types"][0] is Verdict.PASSING


def test_a_nix_host_eval_outside_the_gate_fails_the_types_row(repo: Repo) -> None:
    repo.write("hosts/bee/flake.nix", "{ }")
    repo.write("tools/check-host.sh", "#!/bin/sh\n")
    repo.write("justfile", "check:\n    true\ncheck-host:\n    bash tools/check-host.sh bee\n")
    assert _rows(repo)["stack.nix.types"][0] is Verdict.FAILING


_COVERLET = '<PackageVersion Include="coverlet.MTP" Version="10.1.0" />'
_MS_COVERAGE = '<PackageVersion Include="Microsoft.Testing.Extensions.CodeCoverage" Version="18.12.0" />'


def _coverage_files(repo: Repo, collector: str = _COVERLET) -> None:
    repo.write("App.sln", "")
    repo.write("Directory.Packages.props", collector)
    repo.write(".config/dotnet-tools.json", '{"tools": {"dotnet-reportgenerator-globaltool": {"version": "5.5.11"}}}')
    repo.write("coverage-floor.json", '{"line": 89.0, "branch": 75.0}')
    repo.write("tools/check_coverage.py", "")


def test_dotnet_coverage_floor_run_by_the_gate_passes(repo: Repo) -> None:
    _coverage_files(repo)
    repo.write("justfile", "check: coverage\ncoverage:\n    python3 tools/check_coverage.py cov/Summary.json coverage-floor.json\n")
    assert _rows(repo)["stack.dotnet.coverage"][0] is Verdict.PASSING


@pytest.mark.parametrize(
    ("collector", "verdict"), [(_COVERLET, Verdict.PASSING), (_MS_COVERAGE, Verdict.PASSING), ("", Verdict.NOT_SET_UP)]
)
def test_dotnet_coverage_accepts_either_collector(repo: Repo, collector: str, verdict: Verdict) -> None:
    # lifesim measured Microsoft.Testing.Extensions.CodeCoverage against coverlet.MTP: same coverage, faster (owner ruling 2026-10-29).
    _coverage_files(repo, collector)
    repo.write("justfile", "check: coverage\ncoverage:\n    python3 tools/check_coverage.py cov/Summary.json coverage-floor.json\n")
    assert _rows(repo)["stack.dotnet.coverage"][0] is verdict


def test_dotnet_coverage_floor_outside_the_gate_fails(repo: Repo) -> None:
    _coverage_files(repo)
    repo.write("justfile", "check:\n    true\ncoverage:\n    python3 tools/check_coverage.py cov/Summary.json coverage-floor.json\n")
    assert _rows(repo)["stack.dotnet.coverage"][0] is Verdict.FAILING


def test_a_role_nothing_configures_and_the_gate_never_runs_is_not_set_up(repo: Repo) -> None:
    # homelab (shelf-8bi): no deptry anywhere, yet the row read "deptry set up, but the gate never runs it".
    _python_repo(repo)
    verdict, evidence, _ = _rows(repo)["stack.python-uv.dependencies"]
    assert verdict is Verdict.NOT_SET_UP
    assert "set up, but" not in evidence


_HOOKS = """repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.0
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: local
    hooks:
      - id: deps
        entry: uv run deptry .
        language: system
"""


def test_checks_a_make_gate_runs_through_pre_commit_count_as_run(repo: Repo) -> None:
    # homelab (shelf-0kz): `make check` -> `make lint` -> `pre-commit run --all-files`; every tool lives in the hook config.
    _python_repo(repo)
    repo.write("Makefile", "check: lint\nlint:\n\tuvx pre-commit run --all-files\n")
    repo.write(".pre-commit-config.yaml", _HOOKS)
    rows = _rows(repo)
    assert rows["stack.python-uv.linter"][0] is Verdict.PASSING
    assert rows["stack.python-uv.formatter"][0] is Verdict.PASSING
    assert rows["stack.python-uv.dependencies"][0] is Verdict.PASSING


def test_a_hook_config_the_gate_never_runs_counts_for_nothing(repo: Repo) -> None:
    _python_repo(repo)
    repo.write("Makefile", "check:\n\ttrue\n")
    repo.write(".pre-commit-config.yaml", _HOOKS)
    verdict, evidence, _ = _rows(repo)["stack.python-uv.linter"]
    assert verdict is Verdict.FAILING
    assert "the gate never runs" in evidence


def test_an_unpinned_nix_image_fails_the_nix_toolchain(repo: Repo) -> None:
    # homelab (shelf-2hs): tools/check-host.sh ran `nixos/nix:latest`, which the row's own statement forbids.
    repo.write("hosts/bee/flake.nix", "{ }")
    repo.write("hosts/bee/flake.lock", "{}")
    repo.write("justfile", "check:\n    nix flake lock --no-update-lock-file path:hosts/bee\n")
    assert _rows(repo)["stack.nix.toolchain"][0] is Verdict.PASSING
    repo.write("tools/check-host.sh", "docker run --rm nixos/nix:latest nix eval x\n")
    verdict, evidence, _ = _rows(repo)["stack.nix.toolchain"]
    assert verdict is Verdict.NOT_SET_UP
    assert "nixos/nix:latest" in evidence


def test_pyrefly_must_not_read_ignore_files(repo: Repo) -> None:
    # homelab: in a worktree under .claude/worktrees/ (excluded by .git/info/exclude) pyrefly matched no file and passed.
    _python_repo(repo)
    repo.write("pyproject.toml", _PYPROJECT + '\n[tool.pyrefly]\npreset = "strict"\n')
    verdict, evidence, _ = _rows(repo)["stack.python-uv.types"]
    assert verdict is Verdict.NOT_SET_UP
    assert "use-ignore-files = false" in evidence
