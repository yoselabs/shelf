"""`.agents/skills/onboard-consumer/scripts/onboard.py` — the orchestration script itself.

The operations it calls are tested individually elsewhere (`tests/test_onboard_*.py`); this
file covers only what's specific to the script: shelf-clone resolution, argument handling, and
the self-onboarding refusal below.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _ROOT / ".agents" / "skills" / "onboard-consumer" / "scripts" / "onboard.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "Test")
    (r / "README.md").write_text("hi\n")
    _git(r, "add", "README.md")
    _git(r, "commit", "-qm", "init")
    return r


def _run(*args: str, home: Path) -> subprocess.CompletedProcess[str]:
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(home)}
    return subprocess.run([sys.executable, str(_SCRIPT), *args], capture_output=True, text=True, check=False, env=env)


def test_refuses_to_onboard_the_shelf_onto_itself(tmp_path: Path) -> None:
    result = _run("--repo", str(_ROOT), "--shelf-home", str(_ROOT), home=tmp_path / "home")

    assert result.returncode == 2
    assert "onto itself" in result.stderr
    assert not (_ROOT / "AGENTS.md").read_text().startswith("<!-- BEGIN SHELF RESOLVER BLOCK")


def test_no_shelf_clone_found_is_reported_not_a_crash(repo: Path, tmp_path: Path) -> None:
    # A bare copy, well outside the real shelf clone: onboard.py's own "find my own shelf"
    # fallback (its file location) must not silently resolve to the real repo running this test.
    isolated = tmp_path / "isolated" / "onboard.py"
    isolated.parent.mkdir(parents=True)
    shutil.copy(_SCRIPT, isolated)

    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(tmp_path / "home")}
    Path(env["HOME"]).mkdir(parents=True, exist_ok=True)
    result = subprocess.run([sys.executable, str(isolated), "--repo", str(repo)], capture_output=True, text=True, check=False, env=env)

    assert result.returncode == 2
    assert "could not find a shelf clone" in result.stderr


@pytest.mark.skipif(shutil.which("bd") is None, reason="bd is not installed")
def test_onboards_a_real_consumer_repo_and_exits_zero(repo: Path, tmp_path: Path) -> None:
    (repo / "pyproject.toml").write_text('[project]\nname = "consumer"\nversion = "0.1.0"\n')
    _git(repo, "add", "pyproject.toml")
    _git(repo, "commit", "-qm", "add pyproject")

    result = _run("--repo", str(repo), "--shelf-home", str(_ROOT), home=tmp_path / "home")

    assert result.returncode == 0, result.stdout + result.stderr
    for name in ("guard", "resolver-block", "beads", "linter-preset"):
        assert f"{name}: applied" in result.stdout
