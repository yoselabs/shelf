"""`blueprint gate test`: the gate's tests through any-gate, with the repo's adapter runner; one entry point for a `test` recipe."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from blueprint import gate_test, unit_runner
from blueprint.__main__ import main

if TYPE_CHECKING:
    from pathlib import Path

    from blueprint.gate_test import Execute
    from blueprint.testing import Repo


def test_a_workspace_repo_plans_with_the_adapter_and_runs_what_the_plan_names(repo: Repo) -> None:
    repo.write("packages/a/pyproject.toml", '[project]\nname = "a"\n')
    plan, test = gate_test.commands(repo.root, whole=False, receipts=None, lease_root=None, pytest_args="")
    assert plan is not None
    assert plan[-3:] == ["plan", "--explain", "--plan"]
    assert test[1:4] == ["-m", "any_gate", "test"]
    assert test[test.index("--") + 1 :][1:4] == ["-m", "any_gate_python", "run"]


def test_a_repo_without_packages_runs_its_whole_suite_as_one_unit(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    plan, test = gate_test.commands(repo.root, whole=False, receipts=None, lease_root=None, pytest_args="--cov")
    assert plan is None
    assert gate_test.whole_suite_plan() == "tests\t\n"
    assert test[test.index("--") + 1 :][-1] == "--pytest-args=--cov"


def test_receipts_and_lease_root_pass_through_to_any_gate(repo: Repo, tmp_path: Path) -> None:
    _, test = gate_test.commands(repo.root, whole=False, receipts=tmp_path / "r.json", lease_root=tmp_path / "leases", pytest_args="")
    assert test[test.index("--receipts") + 1] == str(tmp_path / "r.json")
    assert test[test.index("--lease-root") + 1] == str(tmp_path / "leases")


def test_run_pipes_the_plan_into_the_test_command_and_returns_its_exit_code(repo: Repo) -> None:
    repo.write("packages/a/pyproject.toml", '[project]\nname = "a"\n')
    seen: list[tuple[list[str], str | None]] = []

    def fake(cmd: list[str], *, cwd: Path, stdin: str | None, env: dict[str, str]) -> tuple[int, str]:
        seen.append((cmd, stdin))
        return 0, "packages/a/tests\tk1\n" if stdin is None else ""

    assert gate_test.run(repo.root, whole=False, receipts=None, lease_root=None, pytest_args="", execute=fake, env=repo.env) == 0
    assert [stdin for _, stdin in seen] == [None, "packages/a/tests\tk1\n"]


def test_a_failing_plan_is_not_a_pass(repo: Repo) -> None:
    repo.write("packages/a/pyproject.toml", '[project]\nname = "a"\n')

    def fake(cmd: list[str], *, cwd: Path, stdin: str | None, env: dict[str, str]) -> tuple[int, str]:
        return 3, ""

    assert gate_test.run(repo.root, whole=False, receipts=None, lease_root=None, pytest_args="", execute=fake, env=repo.env) == 3


def test_an_override_run_of_a_workspace_writes_no_receipts(repo: Repo) -> None:
    """Pytest arguments (`-m slow`) change what runs: a receipt for them would let a later normal run skip a unit it never ran."""
    repo.write("packages/a/pyproject.toml", '[project]\nname = "a"\n')
    seen: list[str | None] = []

    def fake(cmd: list[str], *, cwd: Path, stdin: str | None, env: dict[str, str]) -> tuple[int, str]:
        seen.append(stdin)
        return 0, "packages/a/tests\tk1\npackages/b/tests\tk2\n" if stdin is None else ""

    assert gate_test.run(repo.root, whole=False, receipts=None, lease_root=None, pytest_args="-m slow", execute=fake, env=repo.env) == 0
    assert seen[1] == "packages/a/tests\t\npackages/b/tests\t\n"  # empty keys: any-gate never skips and never records them


def test_a_normal_run_keeps_the_plans_keys(repo: Repo) -> None:
    repo.write("packages/a/pyproject.toml", '[project]\nname = "a"\n')
    seen: list[str | None] = []

    def fake(cmd: list[str], *, cwd: Path, stdin: str | None, env: dict[str, str]) -> tuple[int, str]:
        seen.append(stdin)
        return 0, "packages/a/tests\tk1\n" if stdin is None else ""

    gate_test.run(repo.root, whole=False, receipts=None, lease_root=None, pytest_args=None, execute=fake, env=repo.env)
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


# ── test-all: the same runner as test, with receipts ignored and marks off (shelf-m0xw, shelf-nvj1) ─────────────────────────────────

_WORKSPACE = '[project]\nname = "x"\n'


def _fake(seen: list[tuple[list[str], str | None]], *, plan: str = "packages/a/tests\tk1\n", fail: str = "") -> Execute:
    def fake(cmd: list[str], *, cwd: Path, stdin: str | None, env: dict[str, str]) -> tuple[int, str]:
        seen.append((cmd, stdin))
        if fail and fail in cmd:
            return 1, ""
        return 0, plan if stdin is None else ""

    return fake


def _whole(repo: Repo, seen: list[tuple[list[str], str | None]], *, plan: str = "packages/a/tests\tk1\n", fail: str = "") -> int:
    return gate_test.run(repo.root, receipts=None, lease_root=None, execute=_fake(seen, plan=plan, fail=fail), env=repo.env, whole=True)


def _runner_args(seen: list[tuple[list[str], str | None]]) -> str:
    """The `--pytest-args` the any-gate runner command got."""
    cmd = next(c for c, stdin in seen if stdin is not None and "any_gate" in c)
    return next(a for a in cmd if a.startswith("--pytest-args="))


def test_test_all_plans_every_suite_of_a_workspace_and_ignores_receipts(repo: Repo) -> None:
    repo.write("packages/a/pyproject.toml", _WORKSPACE)
    seen: list[tuple[list[str], str | None]] = []
    assert _whole(repo, seen, plan="tests\t\npackages/a/tests\tk1\n") == 0
    assert "--all" in seen[0][0]  # the adapter lists every suite, not the ones the change reaches
    assert seen[1][1] == "tests\t\npackages/a/tests\t\n"  # blank keys: nothing is skipped on a receipt, none is recorded


def test_test_all_runs_the_marks_the_per_commit_run_skips(repo: Repo) -> None:
    repo.write("pyproject.toml", _WORKSPACE + '[tool.blueprint.test]\nmarks = "not slow"\n')
    seen: list[tuple[list[str], str | None]] = []
    assert _whole(repo, seen) == 0
    assert "not slow" not in _runner_args(seen)
    seen.clear()
    assert gate_test.run(repo.root, whole=False, receipts=None, lease_root=None, execute=_fake(seen), env=repo.env) == 0
    assert "not slow" in _runner_args(seen)  # the same runner, marks on


def test_test_all_shuffles_only_when_the_repo_asks_for_it(repo: Repo) -> None:
    repo.write("pyproject.toml", _WORKSPACE)
    seen: list[tuple[list[str], str | None]] = []
    _whole(repo, seen)
    assert "randomly" not in _runner_args(seen)
    repo.write("pyproject.toml", _WORKSPACE + "[tool.blueprint.test]\nrandomize = true\n")
    seen.clear()
    _whole(repo, seen)
    assert "-p randomly" in _runner_args(seen)


def test_test_all_has_no_floor_unless_the_repo_declares_one(repo: Repo) -> None:
    repo.write("pyproject.toml", _WORKSPACE)
    seen: list[tuple[list[str], str | None]] = []
    assert _whole(repo, seen) == 0
    assert "--cov" not in _runner_args(seen)
    assert not any("coverage" in cmd for cmd, _ in seen)


@pytest.mark.parametrize("declared", ["[tool.blueprint.test]\nfloor = 80\n", "[tool.coverage.report]\nfail_under = 80\n"])
def test_a_declared_floor_is_judged_once_over_every_stage(repo: Repo, declared: str) -> None:
    repo.write("pyproject.toml", _WORKSPACE + declared)
    seen: list[tuple[list[str], str | None]] = []
    assert _whole(repo, seen) == 0
    args = _runner_args(seen)
    assert "--cov-append" in args
    assert "--cov-fail-under=0" in args  # one stage cannot meet a whole-repo floor
    report = seen[-1][0]
    assert report[-3:] == ["report", "--show-missing", "--fail-under=80"]


def test_a_floor_that_is_not_met_fails_test_all(repo: Repo) -> None:
    repo.write("pyproject.toml", _WORKSPACE + "[tool.blueprint.test]\nfloor = 80\n")
    seen: list[tuple[list[str], str | None]] = []
    assert _whole(repo, seen, fail="--fail-under=80") == 1


def test_a_floor_is_not_judged_when_pytest_args_turn_the_cov_plugin_off(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    repo.write("pyproject.toml", _WORKSPACE + '[tool.blueprint.test]\nfloor = 80\npytest-args = ["-p", "no:cov"]\n')
    seen: list[tuple[list[str], str | None]] = []
    assert _whole(repo, seen) == 0
    assert "--cov" not in _runner_args(seen)
    assert "floor" in capsys.readouterr().err  # said, not silent


def test_test_all_with_pytest_arguments_is_an_override_with_no_floor(repo: Repo) -> None:
    repo.write("pyproject.toml", _WORKSPACE + "[tool.blueprint.test]\nfloor = 80\n")
    seen: list[tuple[list[str], str | None]] = []
    code = gate_test.run(repo.root, receipts=None, lease_root=None, pytest_args="-m slow", execute=_fake(seen), env=repo.env, whole=True)
    assert code == 0
    assert "-m slow" in _runner_args(seen)
    assert "--cov" not in _runner_args(seen)
    assert not any("coverage" in cmd for cmd, _ in seen)


def test_test_all_of_a_unit_repo_hands_the_unit_runner_every_unit_with_marks_off(repo: Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(unit_runner, "combine", lambda *_a, **_k: 0)  # the data is the unit runner's; this judges the plan and the command
    repo.write(
        "pyproject.toml",
        _WORKSPACE
        + '[tool.blueprint.test]\ncoverage = "coverage"\nmarks = "not slow"\n[tool.blueprint.test.units.a]\npaths = ["tests/a"]\n',
    )
    repo.write("tests/a/test_a.py", "def test_a():\n    assert True\n")
    seen: list[tuple[list[str], str | None]] = []
    assert _whole(repo, seen) == 0
    runner = next(c for c, stdin in seen if stdin is not None and "blueprint.unit_runner" in c)
    assert "--whole" in runner
    assert next(stdin for _, stdin in seen if stdin) == "tests/a\t\n"


def test_a_repo_that_turns_the_cov_plugin_off_passes_test_all(repo: Repo, tmp_path: Path) -> None:
    """shelf-nvj1: test-all passed `--cov` to a repo whose pytest-args hold `-p no:cov`, and pytest exited 4."""
    repo.write("pyproject.toml", _WORKSPACE + '[tool.blueprint.test]\nfloor = 80\npytest-args = ["-p", "no:cov"]\n')
    repo.write("tests/test_a.py", "def test_a():\n    assert True\n")
    assert main(["gate", "test-all", "--repo", str(repo.root), "--lease-root", str(tmp_path / "leases")]) == 0


def test_the_blueprint_floor_wins_over_coverage_report_fail_under(repo: Repo) -> None:
    repo.write("pyproject.toml", _WORKSPACE + "[tool.blueprint.test]\nfloor = 80\n[tool.coverage.report]\nfail_under = 95\n")
    seen: list[tuple[list[str], str | None]] = []
    assert _whole(repo, seen) == 0
    assert seen[-1][0][-1] == "--fail-under=80"


def test_the_configured_environment_reaches_every_test_run(repo: Repo) -> None:
    repo.write("pyproject.toml", _WORKSPACE + '[tool.blueprint.test]\nenv = { COVERAGE_CORE = "sysmon" }\n')
    envs: list[dict[str, str]] = []

    def fake(cmd: list[str], *, cwd: Path, stdin: str | None, env: dict[str, str]) -> tuple[int, str]:
        envs.append(env)
        return 0, "tests\t\n" if stdin is None else ""

    assert gate_test.run(repo.root, receipts=None, lease_root=None, execute=fake, env={"INHERITED": "yes"}, whole=True) == 0
    assert envs[-1] == {"INHERITED": "yes", "COVERAGE_CORE": "sysmon"}


# ── slow tests run in `check` when their suite's key changed since the last slow-green receipt (shelf-nqal) ────────────────────────────

_SLOW = _WORKSPACE + '[tool.blueprint.test]\nmarks = "not slow"\n'


def _tests(seen: list[tuple[list[str], str | None]]) -> list[tuple[list[str], str | None]]:
    """The calls that ran tests (the `any_gate test` ones), in order."""
    return [(cmd, stdin) for cmd, stdin in seen if stdin is not None and "any_gate" in cmd and "test" in cmd]


def test_check_runs_the_slow_tests_of_a_suite_whose_key_has_no_slow_receipt(repo: Repo, tmp_path: Path) -> None:
    repo.write("packages/a/pyproject.toml", _WORKSPACE)
    repo.write("pyproject.toml", _SLOW)
    seen: list[tuple[list[str], str | None]] = []
    receipts = tmp_path / "r.json"
    code = gate_test.run(repo.root, whole=False, receipts=receipts, lease_root=None, execute=_fake(seen), env=repo.env)
    assert code == 0
    normal, slow = _tests(seen)
    assert "not slow" in " ".join(normal[0])
    assert normal[0][normal[0].index("--receipts") + 1] == str(receipts)
    assert slow[0][slow[0].index("--receipts") + 1] == str(tmp_path / "slow-r.json")  # its own record: a slow-green receipt
    assert "-m slow" in " ".join(slow[0])
    assert "not slow" not in " ".join(slow[0])
    assert slow[1] == "packages/a/tests\tk1\n"  # the plan's key: unchanged key, receipt found, nothing runs


@pytest.mark.parametrize(
    ("settings", "args", "whole"),
    [
        ('[tool.blueprint.test]\nmarks = "not net"\n', None, False),  # nothing excludes slow
        ("", None, False),  # no marks at all
        ('[tool.blueprint.test]\nmarks = "not slow"\n', "-k x", False),  # an override run
        ('[tool.blueprint.test]\nmarks = "not slow"\n', None, True),  # test-all already ran every mark
    ],
)
def test_no_slow_pass_unless_the_per_commit_run_leaves_slow_out(repo: Repo, settings: str, args: str | None, whole: bool) -> None:
    repo.write("packages/a/pyproject.toml", _WORKSPACE)
    repo.write("pyproject.toml", _WORKSPACE + settings)
    seen: list[tuple[list[str], str | None]] = []
    code = gate_test.run(repo.root, whole=whole, receipts=None, lease_root=None, pytest_args=args, execute=_fake(seen), env=repo.env)
    assert code == 0
    assert len(_tests(seen)) == 1


def test_a_failing_per_commit_run_skips_the_slow_pass(repo: Repo) -> None:
    repo.write("packages/a/pyproject.toml", _WORKSPACE)
    repo.write("pyproject.toml", _SLOW)
    seen: list[tuple[list[str], str | None]] = []

    def fake(cmd: list[str], *, cwd: Path, stdin: str | None, env: dict[str, str]) -> tuple[int, str]:
        seen.append((cmd, stdin))
        return (1, "") if stdin is not None else (0, "packages/a/tests\tk1\n")

    assert gate_test.run(repo.root, whole=False, receipts=None, lease_root=None, execute=fake, env=repo.env) == 1
    assert len(_tests(seen)) == 1


def test_a_unit_repo_runs_its_slow_pass_through_the_unit_runner_without_keeping_data(repo: Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(unit_runner, "combine", lambda *_a, **_k: 0)
    repo.write(
        "pyproject.toml",
        _SLOW + 'coverage = "coverage"\n[tool.blueprint.test.units.a]\npaths = ["tests/a"]\n',
    )
    repo.write("tests/a/test_a.py", "def test_a():\n    assert True\n")
    seen: list[tuple[list[str], str | None]] = []
    assert gate_test.run(repo.root, whole=False, receipts=None, lease_root=None, execute=_fake(seen), env=repo.env) == 0
    slow = [cmd for cmd, stdin in seen if stdin is not None and "blueprint.unit_runner" in cmd][-1]
    assert "--only=slow" in slow
    assert any(a.startswith("--keys=") for a in slow)


def test_editing_a_slow_test_runs_it_in_check_and_a_docs_change_does_not(repo: Repo, tmp_path: Path) -> None:
    """shelf-nqal: the slow tests of a suite run when its key changed since they last passed, never for a change its tests cannot see."""
    count = tmp_path / "count"
    marker = (
        f"from pathlib import Path\nimport pytest\n\n@pytest.mark.slow\ndef test_wheel():\n    Path({str(count)!r}).open('a').write('s')\n"
    )
    repo.write(
        "pyproject.toml",
        '[project]\nname = "x"\n[tool.pytest.ini_options]\nmarkers = ["slow: costs seconds"]\n'
        '[tool.blueprint.test]\nmarks = "not slow"\n[tool.blueprint.test.units.packaging]\npaths = ["tests/packaging"]\n',
    )
    repo.write("tests/packaging/test_wheel_ui.py", marker)
    repo.write("docs/notes.md", "one\n")

    def check() -> int:
        return gate_test.run(
            repo.root, whole=False, receipts=tmp_path / "r.json", lease_root=tmp_path / "leases", cache=tmp_path / "cache", env=repo.env
        )

    assert check() == 0
    assert count.read_text() == "s"  # first run: no slow-green receipt yet
    assert check() == 0
    assert count.read_text() == "s"  # same key: nothing runs
    repo.write("docs/notes.md", "two\n")
    assert check() == 0
    assert count.read_text() == "s"  # a docs-only change does not reach the unit
    repo.write("tests/packaging/test_wheel_ui.py", marker + "# edited\n")
    assert check() == 0
    assert count.read_text() == "ss"  # editing the slow test runs it in check
