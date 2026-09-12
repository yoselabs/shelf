"""The preset-drift check: a consumer matches the shelf's linter config, or says why not.

Resolution 0004 makes the shelf's `pyproject.toml` the preset and says drift is
"acceptable and visible". It was not visible — `linter_preset.py` is append-only
and reports "already current" for a repo missing whole rule families, which is how
ten repos here reached ten rule sets with nobody deciding to.

These tests fix the two properties that matter: a difference fails, and a
difference the consumer *declared* does not. The third is the one an exit code
hides — a check that cannot run must never be reported as a pass.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

DRIFT = Path(__file__).resolve().parents[1] / "tools" / "preset_drift.py"

_SHELF = """\
[tool.ruff.lint]
select = ["F", "E", "RUF"]
ignore = ["ANN401"]

[tool.pyrefly.errors]
deprecated = "error"
implicit-bool = false
"""

_MAKEFILE = "check: lint\n\t@true\nlint:\n\t@true\n"


def _write(root: Path, pyproject: str, makefile: str = _MAKEFILE) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(pyproject)
    (root / "Makefile").write_text(makefile)
    return root


def _run(repo: Path, shelf: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DRIFT), "--repo", str(repo), "--shelf-home", str(shelf)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def shelf(tmp_path: Path) -> Path:
    return _write(tmp_path / "shelf", _SHELF)


def test_an_identical_consumer_passes(tmp_path: Path, shelf: Path) -> None:
    result = _run(_write(tmp_path / "consumer", _SHELF), shelf)
    assert result.returncode == 0, result.stderr


def test_a_missing_rule_family_fails_and_names_it(tmp_path: Path, shelf: Path) -> None:
    consumer = _write(tmp_path / "consumer", _SHELF.replace('"F", "E", "RUF"', '"F", "E"'))
    result = _run(consumer, shelf)
    assert result.returncode == 1
    assert "missing 'RUF'" in result.stderr


def test_an_extra_ignore_fails(tmp_path: Path, shelf: Path) -> None:
    consumer = _write(tmp_path / "consumer", _SHELF.replace('["ANN401"]', '["ANN401", "TRY003"]'))
    result = _run(consumer, shelf)
    assert result.returncode == 1
    assert "extra 'TRY003'" in result.stderr


def test_a_declared_difference_passes(tmp_path: Path, shelf: Path) -> None:
    """The point of the tool: divergence stays the consumer's to choose, once written down."""
    consumer = _write(
        tmp_path / "consumer",
        _SHELF.replace('"F", "E", "RUF"', '"F", "E"') + '\n[tool.shelf-preset]\nruff-select-omitted = ["RUF"]  # reason lives here\n',
    )
    result = _run(consumer, shelf)
    assert result.returncode == 0, result.stderr


def test_a_declaration_covers_only_what_it_names(tmp_path: Path, shelf: Path) -> None:
    consumer = _write(
        tmp_path / "consumer",
        _SHELF.replace('"F", "E", "RUF"', '"F"') + '\n[tool.shelf-preset]\nruff-select-omitted = ["RUF"]\n',
    )
    result = _run(consumer, shelf)
    assert result.returncode == 1
    assert "missing 'E'" in result.stderr
    assert "missing 'RUF'" not in result.stderr


def test_a_pyrefly_kind_set_false_is_a_rejection_not_a_rule(tmp_path: Path, shelf: Path) -> None:
    """`implicit-bool = false` is a recorded decision. A consumer that omits it has not drifted."""
    consumer = _write(tmp_path / "consumer", _SHELF.replace("implicit-bool = false\n", ""))
    result = _run(consumer, shelf)
    assert result.returncode == 0, result.stderr


def test_a_make_target_difference_is_reported(tmp_path: Path, shelf: Path) -> None:
    consumer = _write(tmp_path / "consumer", _SHELF, makefile=_MAKEFILE + "archlint:\n\t@true\n")
    result = _run(consumer, shelf)
    assert result.returncode == 1
    assert "extra 'archlint'" in result.stderr


def test_per_file_ignores_are_not_compared(tmp_path: Path, shelf: Path) -> None:
    """A consumer's tree is not the shelf's. Comparing paths would fail every consumer forever."""
    consumer = _write(
        tmp_path / "consumer",
        _SHELF + '\n[tool.ruff.lint.per-file-ignores]\n"src/whatever/**" = ["ANN"]\n',
    )
    assert _run(consumer, shelf).returncode == 0


def test_no_shelf_clone_is_not_a_pass(tmp_path: Path) -> None:
    consumer = _write(tmp_path / "consumer", _SHELF)
    result = _run(consumer, tmp_path / "nowhere")
    assert result.returncode == 2
    assert "CANNOT VERIFY" in result.stderr


def test_unreadable_config_is_not_a_pass(tmp_path: Path, shelf: Path) -> None:
    consumer = _write(tmp_path / "consumer", "[tool.ruff.lint\nselect = [")
    result = _run(consumer, shelf)
    assert result.returncode == 2
    assert "CANNOT VERIFY" in result.stderr


def test_the_shelf_does_not_compare_against_itself(shelf: Path) -> None:
    result = _run(shelf, shelf)
    assert result.returncode == 0
    assert "this IS the shelf" in result.stdout
