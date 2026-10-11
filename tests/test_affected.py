"""tools/affected.py: a change selects its package, the packages depending on it, and the fitness tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import affected


def _member(repo: Path, directory: str, deps: tuple[str, ...] = (), *, plugin: bool = False) -> None:
    pkg = repo / "packages" / directory
    (pkg / "tests").mkdir(parents=True)
    listed = ", ".join(f'"{d}>=0.1"' for d in deps)
    entry = '\n[project.entry-points.pytest11]\nx = "x"\n' if plugin else ""
    (pkg / "pyproject.toml").write_text(f'[project]\nname = "{directory}"\ndependencies = [{listed}]\n{entry}')


@pytest.fixture
def repo(tmp_path: Path) -> Path:
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
    for changed in (["tests/test_onboard_beads.py"], ["packages/blueprint/src/blueprint/concerns/backlog.py"]):
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


def test_a_suite_that_passed_is_skipped_until_it_or_a_dependency_changes(repo: Path) -> None:
    (repo / "packages/base/src.py").write_text("x = 1\n")
    paths = ["tests", "packages/base/tests", "packages/middle/tests", "packages/leaf/tests"]
    affected.record(repo, paths)
    assert affected.skip_passed(repo, paths) == ["tests"]
    assert affected.skip_passed(repo, ["tests/test_arch.py"]) == ["tests/test_arch.py"]

    (repo / "packages/base/src.py").write_text("x = 2\n")
    assert affected.skip_passed(repo, paths) == ["tests", "packages/base/tests", "packages/middle/tests"]

    (repo / "uv.lock").write_text("changed\n")
    assert affected.skip_passed(repo, paths) == paths
