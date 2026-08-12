"""The `linter-preset` operation (python+uv only) — copies missing tables/targets
from shelf's own `pyproject.toml`/`Makefile`, never touching what's already there.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools"))

from onboard.linter_preset import LinterPresetOperation  # noqa: E402  -- path-injected, after sys.path setup
from onboard.operations import Outcome  # noqa: E402


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    return r


def test_no_pyproject_is_could_not_apply_not_a_failure(repo: Path) -> None:
    result = LinterPresetOperation(repo).run({})

    assert result.outcome == Outcome.COULD_NOT_APPLY
    assert not (repo / "pyproject.toml").exists()


def test_copies_ruff_codespell_coverage_and_dev_group_into_a_bare_pyproject(repo: Path) -> None:
    (repo / "pyproject.toml").write_text('[project]\nname = "consumer"\nversion = "0.1.0"\n')

    result = LinterPresetOperation(repo).run({})

    assert result.outcome == Outcome.APPLIED, result.message
    text = (repo / "pyproject.toml").read_text()
    parsed = tomllib.loads(text)
    assert "[project]" in text, "the consumer's own table must survive untouched"
    assert parsed["project"]["name"] == "consumer"
    assert "ruff" in parsed["tool"]
    assert "lint" in parsed["tool"]["ruff"]
    assert "codespell" in parsed["tool"]
    assert "coverage" in parsed["tool"]
    assert "dev" in parsed["dependency-groups"]


def test_an_existing_ruff_table_is_left_exactly_as_written(repo: Path) -> None:
    original = '[project]\nname = "consumer"\nversion = "0.1.0"\n\n[tool.ruff]\nline-length = 79  # a deliberate, different choice\n'
    (repo / "pyproject.toml").write_text(original)

    result = LinterPresetOperation(repo).run({})

    text = (repo / "pyproject.toml").read_text()
    assert "[tool.ruff]\nline-length = 79" in text, "the consumer's own ruff config was overwritten"
    parsed = tomllib.loads(text)
    assert parsed["tool"]["ruff"]["line-length"] == 79
    assert "lint" not in parsed["tool"]["ruff"], "ruff.lint should not have been force-added under an owned [tool.ruff]"
    # codespell/coverage/dev-group are still genuinely absent, so those DO get copied
    assert "codespell" in parsed["tool"]
    assert result.outcome == Outcome.APPLIED


def test_second_run_is_a_no_op_when_everything_already_copied(repo: Path) -> None:
    (repo / "pyproject.toml").write_text('[project]\nname = "consumer"\nversion = "0.1.0"\n')
    LinterPresetOperation(repo).run({})
    before = (repo / "pyproject.toml").read_text()

    result = LinterPresetOperation(repo).run({})

    assert result.outcome == Outcome.APPLIED
    assert (repo / "pyproject.toml").read_text() == before


def test_copies_missing_makefile_targets_and_leaves_existing_ones_alone(repo: Path) -> None:
    (repo / "pyproject.toml").write_text('[project]\nname = "consumer"\nversion = "0.1.0"\n')
    (repo / "Makefile").write_text("lint:\n\techo my own lint step, not shelf's\n")

    result = LinterPresetOperation(repo).run({})

    assert result.outcome == Outcome.APPLIED, result.message
    make_text = (repo / "Makefile").read_text()
    assert "echo my own lint step" in make_text, "the consumer's own lint target was overwritten"
    assert "guard:" in make_text
    assert "typecheck:" in make_text
    lint_occurrences = make_text.count("\nlint:") + (1 if make_text.startswith("lint:") else 0)
    assert lint_occurrences == 1, "shelf's lint target was appended even though the consumer already had one"


def test_creates_a_makefile_from_scratch_when_absent(repo: Path) -> None:
    (repo / "pyproject.toml").write_text('[project]\nname = "consumer"\nversion = "0.1.0"\n')

    result = LinterPresetOperation(repo).run({})

    assert result.outcome == Outcome.APPLIED, result.message
    make_text = (repo / "Makefile").read_text()
    for target in ("check:", "guard:", "lint:", "format:", "typecheck:", "spell:", "deps:", "test:"):
        assert target in make_text
