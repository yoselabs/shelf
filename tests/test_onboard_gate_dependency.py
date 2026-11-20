"""Onboarding gives a python+uv consumer the `any-gate` dev dependency its gate calls, pinned by git tag (shelf-3pcn.1)."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from onboard import hooks
from onboard.hooks import config_text, ensure_gate_dependency

SOURCE = {
    "git": "https://github.com/yoselabs/shelf",
    "subdirectory": "packages/any-gate",
    "tag": "any-gate-v0.1.1",
}


def test_blueprint_is_added_the_same_way_with_its_own_tag(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "c"\nversion = "0.1.0"\n')
    ensure_gate_dependency(tmp_path)
    data = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    assert "blueprint" in data["dependency-groups"]["dev"]
    assert data["tool"]["uv"]["sources"]["blueprint"] == {**SOURCE, "subdirectory": "packages/blueprint", "tag": "blueprint-v0.2.0"}


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
    ensure_gate_dependency(tmp_path)  # blueprint is added; the repo's own any-gate pin stays as it wrote it
    data = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    assert data["tool"]["uv"]["sources"]["any-gate"] == {"path": "../shelf/packages/any-gate"}
    assert data["dependency-groups"]["dev"].count("any-gate>=0.1") == 1


def test_a_repo_without_a_pyproject_gets_nothing(tmp_path: Path) -> None:
    assert not ensure_gate_dependency(tmp_path)
    assert not (tmp_path / "pyproject.toml").exists()


def test_the_pre_push_hook_runs_the_gate_through_any_gate_in_a_python_repo_and_plainly_elsewhere() -> None:
    entry = "uv run python -m any_gate pre-push --gate check -- uv run just check"
    assert entry in config_text(beads=False, python=True)
    plain = config_text(beads=False, python=False)
    assert entry not in plain
    assert "entry: just check" in plain


def test_the_shelf_packages_the_gate_needs_get_a_tag_source_too(tmp_path: Path) -> None:
    # uv does not carry a git source to the dependencies of a git dependency: any-gate's own shelf packages need one each.
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "c"\nversion = "0.1.0"\n')
    ensure_gate_dependency(tmp_path)
    sources = tomllib.loads((tmp_path / "pyproject.toml").read_text())["tool"]["uv"]["sources"]
    for name in ("any-lease", "process-lock", "atomic-io", "content-digest", "stream-proc"):
        assert sources[name]["subdirectory"] == f"packages/{name}"
        assert sources[name]["tag"].startswith(f"{name}-v")


def test_every_tag_a_consumer_is_pinned_to_for_a_dependency_exists() -> None:
    # The gate packages' own tags are made at release; their dependencies were released before and must still be tagged.
    needed = {hooks.release_tag(d) for name in hooks.GATE_PACKAGES for d in hooks.shelf_closure(name) if d not in hooks.GATE_PACKAGES}
    have = set(subprocess.run(["git", "tag"], cwd=hooks._SHELF_ROOT, capture_output=True, text=True, check=True).stdout.split())
    assert needed <= have, f"tag the release first: {sorted(needed - have)}"


def test_pytest_xdist_joins_the_dev_group_because_the_runner_passes_n(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "c"\nversion = "0.1.0"\n\n[dependency-groups]\ndev = ["ruff"]\n')
    ensure_gate_dependency(tmp_path)
    data = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    assert "pytest-xdist" in data["dependency-groups"]["dev"]
    assert "pytest-xdist" not in data["tool"]["uv"]["sources"], "a PyPI package: no git source"
    before = (tmp_path / "pyproject.toml").read_text()
    assert not ensure_gate_dependency(tmp_path)
    assert (tmp_path / "pyproject.toml").read_text() == before


def test_any_gate_python_declares_the_xdist_its_runner_passes_n_for() -> None:
    manifest = Path(__file__).resolve().parent.parent / "packages" / "any-gate-python" / "pyproject.toml"
    extra = tomllib.loads(manifest.read_text())["project"]["optional-dependencies"]["pytest"]
    assert any(r.startswith("pytest-xdist") for r in extra)
