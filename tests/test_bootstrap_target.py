"""`make bootstrap` / `make bootstrap-verify` — the Makefile targets themselves.

The operations they delegate to are already tested (`tests/test_onboard_*.py`); this file
covers only what's specific to the Makefile fragment: that `make bootstrap` in a real consumer
repo actually invokes the script and surfaces its result, is idempotent at the Make-target
level (not just inside the operations), and does not clobber a foreign hook manager.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "tools"))

from onboard.linter_preset import LinterPresetOperation  # noqa: E402  -- path-injected, after sys.path setup

pytestmark = pytest.mark.skipif(shutil.which("bd") is None, reason="bd is not installed")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "Test")
    (r / "pyproject.toml").write_text('[project]\nname = "consumer"\nversion = "0.1.0"\n')
    _git(r, "add", "pyproject.toml")
    _git(r, "commit", "-qm", "init")
    # The exact Makefile fragment a consumer would have after copying it, per docs/linting.md.
    assert LinterPresetOperation(r).run({}).outcome.value == "applied"
    return r


def _make(repo: Path, target: str, *, home: Path) -> subprocess.CompletedProcess[str]:
    # PATH order matters here: the Makefile invokes bare `python3`, and this Mac's
    # /usr/bin/python3 predates tomllib (3.9) -- put a modern python3 first.
    env = {
        "PATH": f"{Path(sys.executable).parent}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "SHELF_HOME": str(_ROOT),
    }
    return subprocess.run(["make", "-C", str(repo), target], capture_output=True, text=True, check=False, env=env)


def test_make_bootstrap_invokes_the_script_and_applies_every_operation(repo: Path, tmp_path: Path) -> None:
    result = _make(repo, "bootstrap", home=tmp_path / "home")

    assert result.returncode == 0, result.stdout + result.stderr
    for name in ("guard", "resolver-block", "beads", "linter-preset"):
        assert f"{name}: applied" in result.stdout


def test_make_bootstrap_is_idempotent_at_the_target_level(repo: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    first = _make(repo, "bootstrap", home=home)
    assert first.returncode == 0, first.stdout + first.stderr

    second = _make(repo, "bootstrap", home=home)

    assert second.returncode == 0, second.stdout + second.stderr
    assert "linter-preset: applied (verified=True) — already current" in second.stdout


def test_make_bootstrap_verify_is_the_same_call_under_a_different_name(repo: Path, tmp_path: Path) -> None:
    home = tmp_path / "home"
    _make(repo, "bootstrap", home=home)

    result = _make(repo, "bootstrap-verify", home=home)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "guard: applied" in result.stdout


def test_make_bootstrap_does_not_clobber_a_foreign_hook_manager(repo: Path, tmp_path: Path) -> None:
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-commit").write_text('#!/usr/bin/env sh\n. "$(dirname -- "$0")/_/husky.sh"\nnpm test\n')

    result = _make(repo, "bootstrap", home=tmp_path / "home")

    assert result.returncode != 0
    assert "husky" in result.stdout
    assert (hooks / "pre-commit").read_text().startswith("#!/usr/bin/env sh\n."), "the foreign hook was overwritten"


def test_make_check_does_not_depend_on_bootstrap(repo: Path) -> None:
    """D4: content assertions (`check`) must never require environment setup (`bootstrap`)."""
    makefile = (repo / "Makefile").read_text()
    check_line = next(line for line in makefile.splitlines() if line.startswith("check:"))
    assert "bootstrap" not in check_line
