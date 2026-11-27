"""`blueprint gate test`: the gate's tests through any-gate, with the repo's adapter runner; one entry point for a `test` recipe."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint import gate_test

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
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

    def fake(cmd: list[str], *, cwd: Path, stdin: str | None, env: dict[str, str]) -> tuple[int, str]:
        seen.append((cmd, stdin))
        return 0, "packages/a/tests\tk1\n" if stdin is None else ""

    assert gate_test.run(repo.root, receipts=None, lease_root=None, pytest_args="", execute=fake, env=repo.env) == 0
    assert [stdin for _, stdin in seen] == [None, "packages/a/tests\tk1\n"]


def test_a_failing_plan_is_not_a_pass(repo: Repo) -> None:
    repo.write("packages/a/pyproject.toml", '[project]\nname = "a"\n')

    def fake(cmd: list[str], *, cwd: Path, stdin: str | None, env: dict[str, str]) -> tuple[int, str]:
        return 3, ""

    assert gate_test.run(repo.root, receipts=None, lease_root=None, pytest_args="", execute=fake, env=repo.env) == 3


def test_an_override_run_of_a_workspace_writes_no_receipts(repo: Repo) -> None:
    """Pytest arguments (`-m slow`) change what runs: a receipt for them would let a later normal run skip a unit it never ran."""
    repo.write("packages/a/pyproject.toml", '[project]\nname = "a"\n')
    seen: list[str | None] = []

    def fake(cmd: list[str], *, cwd: Path, stdin: str | None, env: dict[str, str]) -> tuple[int, str]:
        seen.append(stdin)
        return 0, "packages/a/tests\tk1\npackages/b/tests\tk2\n" if stdin is None else ""

    assert gate_test.run(repo.root, receipts=None, lease_root=None, pytest_args="-m slow", execute=fake, env=repo.env) == 0
    assert seen[1] == "packages/a/tests\t\npackages/b/tests\t\n"  # empty keys: any-gate never skips and never records them


def test_a_normal_run_keeps_the_plans_keys(repo: Repo) -> None:
    repo.write("packages/a/pyproject.toml", '[project]\nname = "a"\n')
    seen: list[str | None] = []

    def fake(cmd: list[str], *, cwd: Path, stdin: str | None, env: dict[str, str]) -> tuple[int, str]:
        seen.append(stdin)
        return 0, "packages/a/tests\tk1\n" if stdin is None else ""

    gate_test.run(repo.root, receipts=None, lease_root=None, pytest_args=None, execute=fake, env=repo.env)
    assert seen[1] == "packages/a/tests\tk1\n"


def test_the_rest_of_the_command_line_after_two_dashes_is_the_pytest_arguments(repo: Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    import shlex  # noqa: PLC0415

    from blueprint.__main__ import main  # noqa: PLC0415

    seen: dict[str, object] = {}
    monkeypatch.setattr(gate_test, "run", lambda *a, **kw: seen.update(kw) or 0)
    assert main(["gate", "test", "--repo", str(repo.root), "--", "-m", "slow and not net", "-k", "x"]) == 0
    assert shlex.split(str(seen["pytest_args"])) == ["-m", "slow and not net", "-k", "x"]
    seen.clear()
    assert main(["gate", "test", "--repo", str(repo.root)]) == 0
    assert seen["pytest_args"] is None


def test_the_rendered_python_recipes_hand_their_arguments_to_blueprint_unsplit() -> None:
    from blueprint import render  # noqa: PLC0415

    text = (render._TEMPLATES / "python.just").read_text()
    for recipe, verb in (("test", "test"), ("test-all", "test-all")):
        block = text.split(f"\n{recipe} *args:\n", 1)[1].split("\n\n", 1)[0]
        assert f'uv run blueprint gate {verb} -- "$@"' in block
        assert "[positional-arguments]" in text.split(f"\n{recipe} *args:\n", 1)[0].rsplit("\n\n", 1)[1]
