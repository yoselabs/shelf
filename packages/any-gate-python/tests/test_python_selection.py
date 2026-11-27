"""any_gate_python: a change selects its package, the packages depending on it, and the repo's own tests."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import any_gate_python as affected
import pytest
from any_gate_python import graph

if TYPE_CHECKING:
    from pathlib import Path


def _member(repo: Path, directory: str, deps: tuple[str, ...] = (), *, plugin: bool = False) -> None:
    pkg = repo / "packages" / directory
    (pkg / "tests").mkdir(parents=True)
    listed = ", ".join(f'"{d}>=0.1"' for d in deps)
    entry = '\n[project.entry-points.pytest11]\nx = "x"\n' if plugin else ""
    (pkg / "pyproject.toml").write_text(f'[project]\nname = "{directory}"\ndependencies = [{listed}]\n{entry}')


RULES = """
[tool.any-gate.python]
no-effect = ["tests/", "tools/", "docs/", "AGENTS.md"]
repo-tests = "tests"

[tool.any-gate.python.gated]
tests = ["test_onboard_*", "test_bootstrap_target.py"]
inputs = ["tools/onboard/", "tests/conftest.py", "justfile", "pyproject.toml", "uv.lock"]

[tool.any-gate.python.gated.reads]
"test_onboard_beads.py" = ["packages/blueprint/src/blueprint/concerns/beads/backlog.py"]
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(RULES)
    _member(tmp_path, "base")
    _member(tmp_path, "middle", ("base",))
    _member(tmp_path, "top", ("Middle",))
    _member(tmp_path, "leaf")
    _member(tmp_path, "plug", plugin=True)
    return tmp_path


def _pkgs(paths: list[str]) -> set[str]:
    return {p.split("/")[1] for p in paths if p.startswith("packages/")}


def _fitness_tests(repo: Path) -> None:
    (repo / "tests").mkdir()
    for name in ("test_arch.py", "test_onboard_beads.py", "test_bootstrap_target.py"):
        (repo / "tests" / name).write_text("")


def test_an_onboarding_test_runs_alone_when_only_it_or_what_it_reads_changes(repo: Path) -> None:
    _fitness_tests(repo)
    for changed in (["tests/test_onboard_beads.py"], ["packages/blueprint/src/blueprint/concerns/beads/backlog.py"]):
        fitness = [p for p in affected.affected(repo, changed) if p.startswith("tests")]
        assert fitness == ["tests/test_arch.py", "tests/test_onboard_beads.py"], changed
    assert [p for p in affected.affected(repo, ["packages/blueprint/src/blueprint/x.py"]) if p.startswith("tests")] == [
        "tests/test_arch.py"
    ]


@pytest.mark.parametrize(
    ("changed", "runs_onboarding"),
    [
        (["packages/leaf/src/leaf/x.py"], False),
        (["docs/x.md", "AGENTS.md"], False),
        (["tools/onboard/hooks.py"], True),
        (["justfile"], True),
        (["pyproject.toml"], True),
        (["tests/conftest.py"], True),
    ],
)
def test_the_onboarding_tests_run_only_when_an_onboarding_input_changes(repo: Path, changed: list[str], runs_onboarding: bool) -> None:
    # They build real consumer repos (8-14 s each, 2026-10-11); every other fitness test still runs on every change.
    _fitness_tests(repo)
    paths = affected.affected(repo, changed)
    fitness = [p for p in paths if p.startswith("tests")]
    assert fitness == (["tests"] if runs_onboarding else ["tests/test_arch.py"])


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        (["packages/leaf/src/leaf/x.py"], {"leaf"}),
        (["packages/base/src/base/x.py"], {"base", "middle", "top"}),
        (["packages/top/README.md"], {"top"}),
        (["docs/x.md", "tests/test_x.py", "tools/x.py", "AGENTS.md"], set()),
        (["uv.lock"], {"base", "middle", "top", "leaf", "plug"}),
        (["justfile"], {"base", "middle", "top", "leaf", "plug"}),
        (["packages/plug/src/plug/x.py"], {"base", "middle", "top", "leaf", "plug"}),
        ([], set()),
    ],
)
def test_a_change_selects_its_packages_and_their_dependents(repo: Path, changed: list[str], expected: set[str]) -> None:
    assert _pkgs(affected.affected(repo, changed)) == expected


# --- the lock, read per package (ADR 0021, shelf-wctp): a release edits uv.lock, and that must not select every package ---

PINS = {"base": "1", "middle": "1", "top": "1", "leaf": "1", "plug": "1"}
ROOT_PYPROJECT = (
    '[tool.ruff]\nline-length = 100\n\n[dependency-groups]\ndev = ["pytest"]\n\n'
    '[tool.pytest.ini_options]\naddopts = "-q"\ntestpaths = ["packages/base/tests"]\n' + RULES
)


def _write_pins(repo: Path, pins: dict[str, str]) -> None:
    (repo / "uv.lock").write_text("".join(f"{name}={pin}\n" for name, pin in pins.items()))


def pins_exporter(repo: Path, packages: list[str]) -> dict[str, str]:
    """A stand-in for `uv export`: each package's answer is the pin its name has in this tree's uv.lock."""
    pins = dict(line.split("=") for line in (repo / "uv.lock").read_text().split())
    return {name: pins[name] for name in packages}


def _git(repo: Path, *args: str) -> None:
    env = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null", "PATH": os.environ["PATH"], "HOME": str(repo)}
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, env=env, check=True, capture_output=True)


@pytest.fixture
def committed(repo: Path) -> Path:
    """The workspace with a lock and a root pyproject, committed: the base a change is measured against."""
    _write_pins(repo, PINS)
    (repo / "pyproject.toml").write_text(ROOT_PYPROJECT)
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def _selected(repo: Path, changed: list[str]) -> set[str]:
    touched = lambda: affected.lock_touched(repo, "HEAD", pins_exporter)  # noqa: E731
    return _pkgs(affected.affected(repo, changed, lock=touched))


def test_a_lock_change_selects_only_the_packages_whose_resolved_set_changed_and_their_dependents(committed: Path) -> None:
    _write_pins(committed, {**PINS, "middle": "2"})
    assert _selected(committed, ["uv.lock"]) == {"middle", "top"}


def test_a_lock_change_no_package_resolves_differently_selects_no_package(committed: Path) -> None:
    # A release bumps a workspace member's own version in the lock; no package's installed third-party set changes.
    _write_pins(committed, dict(reversed(PINS.items())))
    assert _selected(committed, ["uv.lock"]) == set()


def test_a_root_pyproject_change_in_the_dependency_tables_is_read_like_the_lock(committed: Path) -> None:
    (committed / "pyproject.toml").write_text(ROOT_PYPROJECT.replace('"pytest"', '"pytest", "hypothesis"'))
    _write_pins(committed, {**PINS, "leaf": "2"})
    assert _selected(committed, ["pyproject.toml", "uv.lock"]) == {"leaf"}


def test_a_root_pyproject_change_in_how_tests_run_selects_every_package(committed: Path) -> None:
    # pytest options and coverage settings reach every suite; no export shows them.
    (committed / "pyproject.toml").write_text(ROOT_PYPROJECT.replace('addopts = "-q"', 'addopts = "-q -m not slow"'))
    assert _selected(committed, ["pyproject.toml"]) == set(PINS)


def test_a_root_pyproject_change_no_test_can_see_selects_no_package(committed: Path) -> None:
    # Lint, type and architecture settings, the list of test paths and the workspace edges: whole-repo gate steps read those, not a suite.
    edited = ROOT_PYPROJECT.replace("100", "88").replace('["packages/base/tests"]', '["packages/base/tests", "packages/leaf/tests"]')
    (committed / "pyproject.toml").write_text(
        edited + '[tool.importlinter]\nroot_package = "x"\n[tool.uv.sources]\nleaf = { workspace = true }\n'
    )
    assert _selected(committed, ["pyproject.toml"]) == set()


def test_a_lock_change_whose_export_cannot_be_read_selects_every_package(committed: Path) -> None:
    def broken(_repo: Path, _packages: list[str]) -> dict[str, str]:
        message = "uv failed"
        raise graph.ExportError(message)

    _write_pins(committed, {**PINS, "leaf": "2"})
    touched = lambda: affected.lock_touched(committed, "HEAD", broken)  # noqa: E731
    assert _pkgs(affected.affected(committed, ["uv.lock"], lock=touched)) == set(PINS)


def test_a_package_the_base_did_not_have_counts_as_changed(committed: Path) -> None:
    _member(committed, "fresh")
    _write_pins(committed, {**PINS, "fresh": "1"})
    assert _selected(committed, ["uv.lock"]) == {"fresh"}


def _plan(repo: Path, paths: list[str]) -> dict[str, str]:
    return dict(affected.plan(repo, paths, pins_exporter))


def _no_uv(_repo: Path, _packages: list[str]) -> dict[str, str]:
    message = "uv is not available here"
    raise graph.ExportError(message)


def test_the_plan_gives_each_package_suite_a_key_and_the_fitness_tests_none(committed: Path) -> None:
    plan = _plan(committed, ["tests/test_arch.py", "packages/base/tests", "packages/leaf/tests"])
    assert plan["tests/test_arch.py"] == ""
    assert plan["packages/base/tests"] != plan["packages/leaf/tests"]
    assert all(plan[p] for p in ("packages/base/tests", "packages/leaf/tests"))


def test_a_suites_key_changes_with_its_files_and_its_dependencies_files(committed: Path) -> None:
    before = _plan(committed, ["packages/base/tests", "packages/middle/tests", "packages/leaf/tests"])
    (committed / "packages/base/src.py").write_text("x = 2\n")
    after = _plan(committed, ["packages/base/tests", "packages/middle/tests", "packages/leaf/tests"])
    assert [before[p] != after[p] for p in before] == [True, True, False]


def test_a_suites_key_keeps_when_only_another_packages_resolved_set_changes(committed: Path) -> None:
    paths = ["packages/base/tests", "packages/leaf/tests"]
    before = _plan(committed, paths)
    _write_pins(committed, {**PINS, "leaf": "2"})
    after = _plan(committed, paths)
    assert (before["packages/base/tests"], before["packages/leaf/tests"] != after["packages/leaf/tests"]) == (
        after["packages/base/tests"],
        True,
    )


def test_a_suites_key_changes_when_a_dependencys_resolved_set_changes(committed: Path) -> None:
    paths = ["packages/middle/tests", "packages/top/tests", "packages/leaf/tests"]
    before = _plan(committed, paths)
    _write_pins(committed, {**PINS, "base": "2"})
    after = _plan(committed, paths)
    assert [before[p] != after[p] for p in paths] == [True, True, False]


def test_without_uv_the_lock_and_root_pyproject_stand_in_for_every_suites_key(committed: Path) -> None:
    paths = ["packages/base/tests", "packages/leaf/tests"]
    before = dict(affected.plan(committed, paths, _no_uv))
    (committed / "uv.lock").write_text("changed\n")
    after = dict(affected.plan(committed, paths, _no_uv))
    assert all(before[p] != after[p] for p in paths)


def test_a_selection_over_half_the_suites_gets_an_alarm_that_names_the_count(repo: Path) -> None:
    wide = ["packages/base/tests", "packages/middle/tests", "packages/top/tests"]  # 3 of the 5 suites
    narrow = ["packages/leaf/tests", "packages/plug/tests"]
    alarm = affected.wide_alarm(repo, wide)
    assert alarm is not None
    assert "3 of 5" in alarm
    assert affected.wide_alarm(repo, narrow) is None
    assert affected.wide_alarm(repo, [*narrow, "tests"]) is None  # the repo's own tests are no package suite


def test_every_suite_is_listed_whatever_changed_and_the_repos_own_tests_run_whole(repo: Path) -> None:
    """The release run (`blueprint gate test-all`) plans every suite: the repo's own tests as one folder, then each package's tests."""
    _fitness_tests(repo)
    paths = affected.everything(repo)
    assert paths[0] == "tests"
    assert _pkgs(paths) == {"base", "middle", "top", "leaf", "plug"}
    assert [p for p in paths if p.startswith("tests/")] == []


def test_the_plan_flag_all_lists_every_suite_with_keys(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from any_gate_python.cli import main  # noqa: PLC0415

    _fitness_tests(repo)
    monkeypatch.chdir(repo)
    assert main(["plan", "--repo", str(repo), "--plan", "--all"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "tests\t"
    assert {line.split("\t")[0] for line in lines[1:]} == {f"packages/{d}/tests" for d in ("base", "middle", "top", "leaf", "plug")}
