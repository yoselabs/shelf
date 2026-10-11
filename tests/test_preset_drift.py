"""The preset-drift check: a consumer matches the shelf's linter config, or says why not.

ADR 0004 makes the shelf's `pyproject.toml` the preset and says drift is
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

_JUSTFILE = "check: lint\n\nlint:\n    @true\n"


def _write(root: Path, pyproject: str, justfile: str = _JUSTFILE) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(pyproject)
    (root / "justfile").write_text(justfile)
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


def test_a_recipe_difference_is_reported(tmp_path: Path, shelf: Path) -> None:
    consumer = _write(tmp_path / "consumer", _SHELF, justfile=_JUSTFILE + "\narchlint:\n    @true\n")
    result = _run(consumer, shelf)
    assert result.returncode == 1
    assert "extra 'archlint'" in result.stderr


def test_a_recipe_with_parameters_counts_and_an_assignment_does_not(tmp_path: Path, shelf: Path) -> None:
    consumer = _write(tmp_path / "consumer", _SHELF, justfile=_JUSTFILE + "\nflag := 'x'\n\nrun *args:\n    @true\n")
    result = _run(consumer, shelf)
    assert "extra 'run'" in result.stderr
    assert "flag" not in result.stderr


def test_a_difference_declared_under_the_old_make_targets_key_still_counts(tmp_path: Path, shelf: Path) -> None:
    pyproject = _SHELF + '\n[tool.shelf-preset]\nmake-targets-extra = ["archlint"]\n'
    consumer = _write(tmp_path / "consumer", pyproject, justfile=_JUSTFILE + "\narchlint:\n    @true\n")
    assert _run(consumer, shelf).returncode == 0


def test_a_consumer_still_on_a_makefile_is_compared_by_its_targets(tmp_path: Path, shelf: Path) -> None:
    consumer = _write(tmp_path / "consumer", _SHELF)
    (consumer / "justfile").unlink()
    (consumer / "Makefile").write_text("check: lint\n\t@true\nlint:\n\t@true\nextra:\n\t@true\n")
    result = _run(consumer, shelf)
    assert result.returncode == 1
    assert "extra 'extra'" in result.stderr


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


def test_a_shelf_only_target_missing_from_a_consumer_is_not_drift(tmp_path: Path) -> None:
    shelf = _write(
        tmp_path / "shelf", _SHELF, justfile=_JUSTFILE + "\ncatalog:\n    @true\nadvisory:\n    @true\ntest-browser:\n    @true\n"
    )
    consumer = _write(tmp_path / "consumer", _SHELF)
    result = _run(consumer, shelf)
    assert result.returncode == 0, result.stderr


def test_a_consumer_that_copies_a_shelf_only_recipe_is_not_drift(tmp_path: Path) -> None:
    # a2kay (shelf-cld): it copied the shelf's `check: (gate "check-host")` dispatch and was flagged 'extra gate'.
    dispatch = "\n[private]\ngate target:\n    just {{ target }}\n\ncheck-host:\n    @true\n"
    shelf = _write(tmp_path / "shelf", _SHELF, justfile=_JUSTFILE + dispatch)
    consumer = _write(tmp_path / "consumer", _SHELF, justfile=_JUSTFILE + dispatch)
    result = _run(consumer, shelf)
    assert result.returncode == 0, result.stderr


# ── shelf-bv5: the same config under another ruff is another rule set ─────────
# a2kay's `uv lock --upgrade` moved ruff 0.15 -> 0.17 under an identical config: 30 new findings.


def _lock(root: Path, **versions: str) -> None:
    packages = "".join(f'[[package]]\nname = "{name}"\nversion = "{version}"\n\n' for name, version in versions.items())
    (root / "uv.lock").write_text(f"version = 1\n\n{packages}")


def test_a_consumer_on_another_ruff_fails_and_names_both_versions(tmp_path: Path, shelf: Path) -> None:
    consumer = _write(tmp_path / "consumer", _SHELF)
    _lock(shelf, ruff="0.15.20", pyrefly="0.40.0")
    _lock(consumer, ruff="0.17.0", pyrefly="0.40.0")
    result = _run(consumer, shelf)
    assert result.returncode == 1
    assert "ruff 0.17.0" in result.stderr
    assert "0.15.20" in result.stderr
    assert "pyrefly" not in result.stderr


def test_matching_linter_versions_pass(tmp_path: Path, shelf: Path) -> None:
    consumer = _write(tmp_path / "consumer", _SHELF)
    _lock(shelf, ruff="0.15.20")
    _lock(consumer, ruff="0.15.20")
    assert _run(consumer, shelf).returncode == 0


def test_a_declared_linter_version_difference_passes(tmp_path: Path, shelf: Path) -> None:
    consumer = _write(tmp_path / "consumer", _SHELF + '\n[tool.shelf-preset]\nlinter-versions-differ = ["ruff"]\n')
    _lock(shelf, ruff="0.15.20")
    _lock(consumer, ruff="0.17.0")
    assert _run(consumer, shelf).returncode == 0
