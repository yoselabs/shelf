"""The python stack's steps as engine commands: paths and extra steps are data in pyproject.toml, so a repo defines no recipe of its own."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from blueprint import gate_py, render
from blueprint.__main__ import main

if TYPE_CHECKING:
    from blueprint.testing import Repo

_PYPROJECT = """\
[project]
name = "x"

[tool.blueprint.gate]
release-gate = true
lint-paths = ["src", "tests"]
spell-paths = ["src", "README.md"]
steps = ["arch", "tag-check"]

[tool.blueprint.test]
floor = 80

[tool.ruff]
line-length = 100
"""


def _repo(repo: Repo) -> None:
    repo.write("pyproject.toml", _PYPROJECT)
    repo.write("uv.lock", "")
    repo.write("src/a.py", "x = 1\n")
    repo.write("README.md", "hello\n")
    repo.write("tests/test_a.py", "def test_a():\n    assert True\n")


def test_the_repos_extra_steps_join_check_and_their_whole_form_joins_check_all(repo: Repo) -> None:
    _repo(repo)
    base = render.parts(repo.root)[".blueprint/base.just"]
    assert '"test" "arch" "tag-check")' in base
    assert '"test-all" "arch" "tag-check")' in base
    assert '"lint-changed"' in base
    assert '"lint" "typecheck" "spell"' in base  # the release gate runs the whole form of the changed-only steps


def test_check_all_runs_the_extension_point_too(repo: Repo) -> None:
    _repo(repo)
    base = render.parts(repo.root)[".blueprint/base.just"]
    assert "check-all: beads-lint" in base
    assert base.split("check-all:")[1].splitlines()[0].endswith("check-extra")


@pytest.mark.parametrize("setting", ["", "release-gate = false", 'release-gate = "true"', "release-gate = 1", "release-gate = true"])
def test_only_an_explicit_boolean_enables_the_release_gate(repo: Repo, setting: str) -> None:
    repo.write("pyproject.toml", f"[tool.blueprint.gate]\n{setting}\n")
    assert gate_py.release_gate(repo.root) is (setting == "release-gate = true")


def test_lint_reads_only_the_declared_paths(repo: Repo) -> None:
    _repo(repo)
    repo.write("src/bad.py", "import os\n")
    repo.write("scripts/outside.py", "import os\n")
    assert gate_py.lint(repo.root) == 1  # src/bad.py: unused import, found
    (repo.root / "src" / "bad.py").unlink()
    assert gate_py.lint(repo.root) == 0  # scripts/ is not a declared path


def test_the_changed_form_skips_when_nothing_changed(
    repo: Repo, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _repo(repo)
    monkeypatch.setattr(gate_py, "changed", lambda *_a, **_k: [])
    assert gate_py.lint_changed(repo.root) == 0
    assert "skipped lint" in capsys.readouterr().out


def test_the_changed_form_checks_everything_when_no_base_can_be_told(repo: Repo) -> None:
    _repo(repo)
    repo.write("src/bad.py", "import os\n")
    assert gate_py.lint_changed(repo.root) == 1  # no upstream: run too much rather than too little


def test_spell_reads_the_declared_paths(repo: Repo) -> None:
    _repo(repo)
    assert gate_py.spell(repo.root) == 0
    repo.write("src/typo.py", "# a " + "re" + "cie" + "ve typo\n")
    assert gate_py.spell(repo.root) != 0


def test_test_all_takes_its_floor_from_the_repo(repo: Repo) -> None:
    _repo(repo)
    cmd = gate_py.test_all_command(repo.root, {"HOME": str(repo.root)})
    assert "--cov-fail-under=80" in cmd
    assert "-n" in cmd


def test_test_all_has_a_default_floor(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    assert "--cov-fail-under=65" in gate_py.test_all_command(repo.root, {"HOME": str(repo.root)})


@pytest.mark.parametrize("args", ['["-q"]', '["-n", "2", "--dist", "loadgroup", "-q"]'])
def test_test_all_uses_configured_arguments_and_marks_without_duplicate_workers(repo: Repo, args: str) -> None:
    _repo(repo)
    repo.write("pyproject.toml", _PYPROJECT.replace("floor = 80", f'floor = 80\npytest-args = {args}\nmarks = "not slow"'))
    command = gate_py.test_all_command(repo.root, repo.env)
    assert command.count("-n") == 1
    assert command[command.index("-n") + 1] == ("2" if '"2"' in args else "auto")
    assert "-q" in command
    assert command[command.index("-m", command.index("pytest")) + 1] == "not slow"


def test_test_all_adds_configured_environment_to_the_supplied_environment(repo: Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    _repo(repo)
    repo.write("pyproject.toml", _PYPROJECT.replace("floor = 80", 'floor = 80\nenv = { COVERAGE_CORE = "sysmon" }'))
    seen: dict[str, object] = {}

    def execute(command: list[str], **kwargs: object) -> SimpleNamespace:
        assert "pytest" in command
        assert kwargs["cwd"] == repo.root
        seen.update(kwargs)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(gate_py.subprocess, "run", execute)
    assert gate_py.test_all(repo.root, {"INHERITED": "yes", "COVERAGE_CORE": "old"}) == 0
    assert seen["env"] == {"INHERITED": "yes", "COVERAGE_CORE": "sysmon"}


def test_test_all_takes_its_floor_from_coverage_report(repo: Repo) -> None:
    repo.write("pyproject.toml", "[tool.coverage.report]\nfail_under = 87.5\n")
    assert "--cov-fail-under=87.5" in gate_py.test_all_command(repo.root, {"HOME": str(repo.root)})


def test_test_all_prefers_the_blueprint_floor_over_coverage_report(repo: Repo) -> None:
    repo.write("pyproject.toml", _PYPROJECT + "\n[tool.coverage.report]\nfail_under = 95\n")
    assert "--cov-fail-under=80" in gate_py.test_all_command(repo.root, {"HOME": str(repo.root)})


def test_the_lease_root_follows_the_environment() -> None:
    assert str(gate_py.lease_root({"GATE_LEASE_ROOT": "/l"})) == "/l"
    assert str(gate_py.lease_root({"XDG_CACHE_HOME": "/c"})) == "/c/gate-leases"


def test_the_cli_exposes_the_steps(repo: Repo) -> None:
    _repo(repo)
    assert main(["gate", "format", "--repo", str(repo.root)]) == 0
    assert main(["gate", "lint", "--repo", str(repo.root)]) == 0
