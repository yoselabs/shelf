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
    assert paths[0] == "tests"
    return {p.split("/")[1] for p in paths[1:]}


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        (["packages/leaf/src/leaf/x.py"], {"leaf"}),
        (["packages/base/src/base/x.py"], {"base", "middle", "top"}),
        (["packages/top/README.md"], {"top"}),
        (["docs/x.md", "tests/test_x.py", "tools/x.py", "AGENTS.md"], set()),
        (["uv.lock"], {"base", "middle", "top", "leaf", "plug"}),
        (["Makefile"], {"base", "middle", "top", "leaf", "plug"}),
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

    (repo / "packages/base/src.py").write_text("x = 2\n")
    assert affected.skip_passed(repo, paths) == ["tests", "packages/base/tests", "packages/middle/tests"]

    (repo / "uv.lock").write_text("changed\n")
    assert affected.skip_passed(repo, paths) == paths
