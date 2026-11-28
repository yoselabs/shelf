"""`layout.root-files-in-config` (ADR 0035): tool config files and caches live in `.config/` and `.cache/`, not at the repo root."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_ROW = "layout.root-files-in-config"
_PYPROJECT = (
    '[project]\nname = "app"\nversion = "0"\nrequires-python = ">=3.12"\n'
    '[tool.ruff]\ncache-dir = ".cache/ruff"\n'
    '[tool.coverage.run]\ndata_file = ".cache/coverage"\n'
)


def _python(repo: Repo, pyproject: str = _PYPROJECT) -> None:
    repo.write("pyproject.toml", pyproject)
    repo.write("uv.lock", "version = 1\n")
    repo.write("src/app/__init__.py", "")
    repo.write("tests/test_app.py", "")


def _row(repo: Repo):
    rows = {r.id: r for r in run(repo.root, concern="layout", env=repo.env, today=date(2026, 12, 1)).rows}
    return rows[_ROW]


def test_a_repo_with_its_config_in_config_and_caches_in_cache_passes(repo: Repo) -> None:
    _python(repo)
    repo.write(".config/gitleaks.toml", "")
    assert _row(repo).verdict is Verdict.PASSING


@pytest.mark.parametrize(
    ("root", "moved"),
    [
        (".gitleaks.toml", ".config/gitleaks.toml"),
        (".hadolint.yaml", ".config/hadolint.yaml"),
        (".yamlfmt.yaml", ".config/yamlfmt.yaml"),
        (".yamlfmt", ".config/yamlfmt.yaml"),
        (".dclintrc", ".config/dclintrc.json"),
        (".dclintrc.json", ".config/dclintrc.json"),
        ("typos.toml", ".config/typos.toml"),
        (".typos.toml", ".config/typos.toml"),
    ],
)
def test_a_movable_root_file_fails_and_the_remedy_names_the_git_mv(repo: Repo, root: str, moved: str) -> None:
    _python(repo)
    repo.write(root, "")
    row = _row(repo)
    assert row.verdict is Verdict.FAILING
    assert f"git mv {root} {moved}" in row.remediation
    assert root in row.evidence


def test_every_movable_file_is_named_in_one_row(repo: Repo) -> None:
    _python(repo)
    repo.write(".gitleaks.toml", "")
    repo.write(".hadolint.yaml", "")
    row = _row(repo)
    assert "git mv .gitleaks.toml .config/gitleaks.toml" in row.remediation
    assert "git mv .hadolint.yaml .config/hadolint.yaml" in row.remediation


def test_a_tool_that_may_not_move_is_never_listed(repo: Repo) -> None:
    _python(repo)
    for name in ("justfile", "mise.toml", ".pre-commit-config.yaml", "gate-inputs.toml", "package.json", "Dockerfile", "compose.yml"):
        repo.write(name, "")
    row = _row(repo)
    assert row.verdict is Verdict.PASSING, row.remediation


def test_a_cache_setting_left_at_the_tool_default_fails_with_the_exact_setting(repo: Repo) -> None:
    _python(repo, '[project]\nname = "app"\nversion = "0"\n[tool.ruff]\nline-length = 100\n[tool.pytest.ini_options]\ntimeout = 5\n')
    row = _row(repo)
    assert row.verdict is Verdict.FAILING
    assert 'cache-dir = ".cache/ruff"' in row.remediation
    assert "cache_dir" not in row.remediation  # pytest: `-p no:cacheprovider` makes the option unknown (ADR 0035)
    assert "[tool.coverage.run]" not in row.remediation  # the repo does not use coverage config: nothing to move


def test_a_cache_in_another_config_file_is_not_judged(repo: Repo) -> None:
    _python(repo, '[project]\nname = "app"\nversion = "0"\n[tool.ruff]\nline-length = 100\n')
    repo.write("ruff.toml", "line-length = 100\n")
    repo.write("pytest.ini", "[pytest]\n")
    assert _row(repo).verdict is Verdict.PASSING


def test_a_repo_with_no_pyproject_and_no_movable_file_passes(repo: Repo) -> None:
    repo.write("README.md", "x\n")
    assert _row(repo).verdict in {Verdict.PASSING, Verdict.NOT_APPLICABLE}


def test_a_dated_waiver_passes_the_row(repo: Repo) -> None:
    _python(repo)
    repo.write(".gitleaks.toml", "")
    repo.write(
        "docs/blueprint/blueprint.toml",
        f'[[tool.blueprint.waivers]]\nid = "{_ROW}"\nreason = "moves with the next a2kay change"\n'
        f'since = "2026-12-01"\nuntil = "2026-12-31"\n',
    )
    row = _row(repo)
    assert row.verdict is Verdict.PASSING
    assert "waived until 2026-12-31" in row.evidence


def test_the_remedy_says_a_flag_is_needed_in_every_recipe(repo: Repo) -> None:
    _python(repo)
    repo.write(".hadolint.yaml", "")
    assert "flag is needed in every recipe" in _row(repo).remediation
