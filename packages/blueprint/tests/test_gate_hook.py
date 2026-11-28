"""`blueprint gate hook`: the one commit-hook process. It runs what five hooks ran (secret scan, guard, preset drift, ruff check,
ruff format) over the staged files, so a commit starts one `uv run`; every refusal of the five still refuses."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from blueprint.testing import run_cli

if TYPE_CHECKING:
    import subprocess

    from blueprint.testing import Repo

# Built at run time: no source line holds a token-shaped string for the scanner to flag.
_LEAK = 'aws_key = "' + "AKIA" + "Z7VRSQ2WKNBTXPLM" + '"\n'
_LOCAL_SOURCE = (
    '[project]\nname = "c"\nversion = "0.1.0"\n\n[tool.uv.sources]\nanyllm = { path = "../shelf/packages/anyllm", editable = true }\n'
)
_PYPROJECT = '[project]\nname = "c"\nversion = "0.1.0"\n'


def _stage(repo: Repo, rel: str, text: str) -> None:
    repo.write(rel, text)
    repo.git("add", rel)


def _hook(repo: Repo) -> subprocess.CompletedProcess[str]:
    return run_cli(["gate", "hook"], cwd=repo.root)


def test_a_clean_staged_change_passes(repo: Repo) -> None:
    _stage(repo, "a.py", "x = 1\n")
    assert _hook(repo).returncode == 0


def test_a_staged_secret_is_refused(repo: Repo) -> None:
    _stage(repo, "a.py", _LEAK)
    result = _hook(repo)
    assert result.returncode == 1
    assert "aws-access-token" in result.stderr


def test_a_staged_local_shelf_source_is_refused(repo: Repo) -> None:
    _stage(repo, "pyproject.toml", _LOCAL_SOURCE)
    result = _hook(repo)
    assert result.returncode == 1
    assert "anyllm" in result.stderr


def test_a_staged_ruff_violation_is_refused(repo: Repo) -> None:
    _stage(repo, "a.py", "import os\n")
    assert _hook(repo).returncode == 1


def test_a_staged_unformatted_file_is_refused(repo: Repo) -> None:
    _stage(repo, "a.py", "x   =   1\n")
    assert _hook(repo).returncode == 1


def test_staged_preset_drift_is_refused(repo: Repo) -> None:
    _stage(repo, "pyproject.toml", _PYPROJECT + '\n[tool.ruff.lint]\nselect = ["E"]\nignore = ["ALL"]\n')
    result = _hook(repo)
    assert result.returncode == 1
    assert "preset-drift" in result.stderr


def test_preset_is_judged_only_when_pyproject_is_staged(repo: Repo) -> None:
    repo.write("pyproject.toml", _PYPROJECT + '\n[tool.ruff.lint]\nselect = ["E"]\nignore = ["ALL"]\n')
    _stage(repo, "a.py", "x = 1\n")
    assert _hook(repo).returncode == 0


def test_ruff_reads_only_the_declared_lint_paths(repo: Repo) -> None:
    _stage(repo, "pyproject.toml", _PYPROJECT + '\n[tool.blueprint.gate]\nlint-paths = ["src"]\n')
    _stage(repo, "scratch/a.py", "import os\n")
    result = _hook(repo)
    assert "scratch" not in result.stderr + result.stdout


def test_the_worst_exit_code_wins_and_every_check_still_reports(repo: Repo) -> None:
    _stage(repo, "pyproject.toml", _LOCAL_SOURCE)
    _stage(repo, "a.py", "import os\n")
    result = _hook(repo)
    assert result.returncode == 1
    assert "anyllm" in result.stderr
    assert "F401" in result.stdout + result.stderr


def test_a_git_failure_fails_the_hook_instead_of_skipping_ruff(tmp_path: Path) -> None:
    result = run_cli(["gate", "hook", "--repo", str(tmp_path)])
    assert result.returncode != 0
    assert "git diff --cached failed" in result.stderr


def test_the_rendered_hook_entry_runs_frozen() -> None:
    text = (Path(__file__).parents[1] / "src/blueprint/recipes/pre-commit-config.yaml").read_text()
    assert "entry: uv run --frozen blueprint gate hook" in text
