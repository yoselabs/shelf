"""`blueprint test`: the gate's tests through any-gate, with the repo's adapter runner; one entry point for a `test` recipe."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint import gate_test

if TYPE_CHECKING:
    from pathlib import Path

    from blueprint.testing import Repo


def test_a_workspace_repo_plans_with_the_adapter_and_runs_what_the_plan_names(repo: Repo) -> None:
    repo.write("packages/a/pyproject.toml", '[project]\nname = "a"\n')
    plan, test = gate_test.commands(repo.root, receipts=None, lease_root=None, pytest_args="")
    assert plan is not None
    assert plan[-3:] == ["plan", "--explain", "--plan"]
    assert test[1:4] == ["-m", "any_gate", "test"]
    assert test[test.index("--") + 1 :][1:4] == ["-m", "any_gate_python", "run"]


def test_a_repo_without_packages_runs_its_whole_suite_as_one_unit(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    plan, test = gate_test.commands(repo.root, receipts=None, lease_root=None, pytest_args="--cov")
    assert plan is None
    assert gate_test.whole_suite_plan() == "tests\t\n"
    assert test[test.index("--") + 1 :][-1] == "--pytest-args=--cov"


def test_receipts_and_lease_root_pass_through_to_any_gate(repo: Repo, tmp_path: Path) -> None:
    _, test = gate_test.commands(repo.root, receipts=tmp_path / "r.json", lease_root=tmp_path / "leases", pytest_args="")
    assert test[test.index("--receipts") + 1] == str(tmp_path / "r.json")
    assert test[test.index("--lease-root") + 1] == str(tmp_path / "leases")


def test_run_pipes_the_plan_into_the_test_command_and_returns_its_exit_code(repo: Repo) -> None:
    repo.write("packages/a/pyproject.toml", '[project]\nname = "a"\n')
    seen: list[tuple[list[str], str | None]] = []

    def fake(cmd: list[str], *, cwd: Path, stdin: str | None) -> tuple[int, str]:
        seen.append((cmd, stdin))
        return 0, "packages/a/tests\tk1\n" if stdin is None else ""

    assert gate_test.run(repo.root, receipts=None, lease_root=None, pytest_args="", execute=fake) == 0
    assert [stdin for _, stdin in seen] == [None, "packages/a/tests\tk1\n"]


def test_a_failing_plan_is_not_a_pass(repo: Repo) -> None:
    repo.write("packages/a/pyproject.toml", '[project]\nname = "a"\n')

    def fake(cmd: list[str], *, cwd: Path, stdin: str | None) -> tuple[int, str]:
        return 3, ""

    assert gate_test.run(repo.root, receipts=None, lease_root=None, pytest_args="", execute=fake) == 3
