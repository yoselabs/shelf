"""Onboarding gives a python+uv consumer the `any-gate` dev dependency its gate calls, pinned by git tag (shelf-3pcn.1)."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from onboard.hooks import config_text, ensure_gate_dependency

SOURCE = {
    "git": "https://github.com/yoselabs/shelf",
    "subdirectory": "packages/any-gate",
    "tag": "any-gate-v0.1.0",
}


def _wired(repo: Path) -> tuple[list[str], dict[str, object]]:
    data = tomllib.loads((repo / "pyproject.toml").read_text())
    return data["dependency-groups"]["dev"], data["tool"]["uv"]["sources"]["any-gate"]


@pytest.mark.parametrize(
    "start",
    [
        '[project]\nname = "c"\nversion = "0.1.0"\n',
        '[project]\nname = "c"\nversion = "0.1.0"\n\n[dependency-groups]\nother = ["x"]\n',
        '[project]\nname = "c"\nversion = "0.1.0"\n\n[dependency-groups]\ndev = ["ruff", "pyrefly"]\n',
        '[project]\nname = "c"\nversion = "0.1.0"\n\n[dependency-groups]\ndev = [\n    "ruff",\n    "pyrefly",\n]\n',
        '[project]\nname = "c"\nversion = "0.1.0"\n\n[tool.uv.sources]\nthing = { path = "../thing" }\n',
    ],
    ids=["bare", "group-without-dev", "one-line-dev", "multi-line-dev", "existing-sources"],
)
def test_the_dependency_and_its_tag_pin_are_added_to_any_pyproject(tmp_path: Path, start: str) -> None:
    (tmp_path / "pyproject.toml").write_text(start)
    assert ensure_gate_dependency(tmp_path)
    group, source = _wired(tmp_path)
    assert "any-gate" in group
    assert source == SOURCE
    before = tomllib.loads(start)
    after = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    assert after["project"] == before["project"]  # nothing else is touched


def test_a_second_run_changes_nothing(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "c"\nversion = "0.1.0"\n')
    ensure_gate_dependency(tmp_path)
    written = (tmp_path / "pyproject.toml").read_text()
    assert not ensure_gate_dependency(tmp_path)
    assert (tmp_path / "pyproject.toml").read_text() == written


def test_a_repo_that_pinned_it_another_way_is_left_alone(tmp_path: Path) -> None:
    text = (
        '[project]\nname = "c"\nversion = "0.1.0"\n\n[dependency-groups]\ndev = ["any-gate>=0.1"]\n\n'
        '[tool.uv.sources]\nany-gate = { path = "../shelf/packages/any-gate" }\n'
    )
    (tmp_path / "pyproject.toml").write_text(text)
    assert not ensure_gate_dependency(tmp_path)
    assert (tmp_path / "pyproject.toml").read_text() == text


def test_a_repo_without_a_pyproject_gets_nothing(tmp_path: Path) -> None:
    assert not ensure_gate_dependency(tmp_path)
    assert not (tmp_path / "pyproject.toml").exists()


def test_the_pre_push_hook_runs_the_gate_through_any_gate_in_a_python_repo_and_plainly_elsewhere() -> None:
    entry = "uv run python -m any_gate pre-push --gate check -- uv run just check"
    assert entry in config_text(beads=False, python=True)
    plain = config_text(beads=False, python=False)
    assert entry not in plain
    assert "entry: just check" in plain
