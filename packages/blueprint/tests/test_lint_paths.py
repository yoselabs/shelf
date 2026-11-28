"""shelf-pv71: `lint-paths` must cover every tracked .py, or a new folder goes unlinted."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint.model import Verdict
from blueprint.runner import Row, run

if TYPE_CHECKING:
    from blueprint.testing import Repo

ROW = "gate.lint-paths-cover-python"


def _row(repo: Repo) -> Row:
    return {r.id: r for r in run(repo.root, concern="gate", env=repo.env).rows}[ROW]


def _setup(repo: Repo, paths: str) -> None:
    repo.write("pyproject.toml", f'[project]\nname = "x"\n[tool.blueprint.gate]\nlint-paths = {paths}\n')
    repo.write("packages/a/m.py", "x = 1\n")
    repo.write("tools/t.py", "x = 1\n")
    repo.write("conftest.py", "x = 1\n")
    repo.commit()


def test_no_lint_paths_means_the_repo_root_and_is_not_applicable(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    repo.write("newdir/m.py", "x = 1\n")
    repo.commit()
    assert _row(repo).verdict is Verdict.NOT_APPLICABLE


def test_paths_covering_every_tracked_py_pass(repo: Repo) -> None:
    _setup(repo, '["packages", "tools", "conftest.py"]')
    assert _row(repo).verdict is Verdict.PASSING


def test_a_tracked_py_outside_the_paths_fails_and_names_it(repo: Repo) -> None:
    _setup(repo, '["packages", "conftest.py"]')
    row = _row(repo)
    assert row.verdict is Verdict.FAILING
    assert "tools" in row.evidence
    assert "lint-paths" in row.remediation


def test_dot_covers_everything(repo: Repo) -> None:
    _setup(repo, '["."]')
    assert _row(repo).verdict is Verdict.PASSING


def test_a_folder_prefix_is_not_a_sibling_name(repo: Repo) -> None:
    _setup(repo, '["pack", "tools", "conftest.py"]')  # `pack` is not `packages`
    assert _row(repo).verdict is Verdict.FAILING


def test_a_file_ruff_excludes_is_not_unlinted(repo: Repo) -> None:
    repo.write(
        "pyproject.toml",
        '[project]\nname = "x"\n[tool.ruff]\nextend-exclude = ["tools/gen"]\n[tool.blueprint.gate]\nlint-paths = ["packages"]\n',
    )
    repo.write("packages/a/m.py", "x = 1\n")
    repo.write("tools/gen/t.py", "x = 1\n")
    repo.commit()
    assert _row(repo).verdict is Verdict.PASSING


def test_dot_slash_and_trailing_slash_spellings_cover_like_the_plain_ones(repo: Repo) -> None:
    _setup(repo, '["./packages", "tools/", "./conftest.py"]')
    assert _row(repo).verdict is Verdict.PASSING
