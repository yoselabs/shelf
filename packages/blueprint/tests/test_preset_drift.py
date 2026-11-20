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
import tomllib
from typing import TYPE_CHECKING

import pytest
from blueprint import preset

if TYPE_CHECKING:
    from pathlib import Path

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
    reference = shelf / "reference.toml"
    if (shelf / "pyproject.toml").is_file():
        reference.write_text(preset.render(preset.snapshot(shelf)))
    return subprocess.run(
        [sys.executable, "-m", "blueprint", "gate", "preset", "--repo", str(repo), "--reference", str(reference)],
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


def test_the_justfile_is_not_compared_here(tmp_path: Path, shelf: Path) -> None:
    """Its parts are rendered and `blueprint gate render --check` is their drift check (ADR 0029); a recipe set is no axis of the preset."""
    consumer = _write(tmp_path / "consumer", _SHELF, justfile=_JUSTFILE + "\narchlint:\n    @true\n")
    (consumer / "Makefile").write_text("extra:\n\t@true\n")
    result = _run(consumer, shelf)
    assert result.returncode == 0, result.stderr


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
    # The shelf is the repo holding the snapshot in its blueprint package.
    (shelf / "packages" / "blueprint" / "src" / "blueprint").mkdir(parents=True)
    (shelf / "packages" / "blueprint" / "src" / "blueprint" / "preset.toml").write_text("")
    result = subprocess.run(
        [sys.executable, "-m", "blueprint", "gate", "preset", "--repo", str(shelf)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "this IS the shelf" in result.stdout


def test_a_consumer_is_compared_with_the_packaged_snapshot_by_default(tmp_path: Path) -> None:
    consumer = _write(tmp_path / "consumer", _SHELF)
    result = subprocess.run(
        [sys.executable, "-m", "blueprint", "gate", "preset", "--repo", str(consumer)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 1  # a three-rule config is far from the shelf's
    assert "missing" in result.stderr


def test_a_snapshot_round_trips_through_its_text(shelf: Path) -> None:
    snap = preset.snapshot(shelf)
    assert tomllib.loads(preset.render(snap)) == snap


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


# ── the EFFECTIVE ruff config: ruff.toml wins over pyproject, as ruff does (shelf-166r) ──
# OGY showed 252 errors under the preset while `blueprint gate preset` passed: a ruff.toml shadowed the preset block in pyproject.toml.

_OLD_RULES = '[lint]\nselect = ["F"]\nignore = []\n'


@pytest.mark.parametrize("name", ["ruff.toml", ".ruff.toml"])
def test_a_ruff_toml_shadowing_the_preset_block_fails_and_is_what_gets_compared(tmp_path: Path, shelf: Path, name: str) -> None:
    consumer = _write(tmp_path / "consumer", _SHELF)
    (consumer / name).write_text(_OLD_RULES)
    result = _run(consumer, shelf)
    assert result.returncode == 1
    assert f"{name} shadows" in result.stderr
    assert "missing 'RUF'" in result.stderr, "the preset must judge the config ruff reads, not the dead block"


def test_a_declared_shadow_passes_when_the_effective_config_matches(tmp_path: Path, shelf: Path) -> None:
    declaration = '\n[tool.shelf-preset]\nruff-config-shadows = ["ruff.toml"]  # one file for the editor too\n'
    consumer = _write(tmp_path / "consumer", _SHELF + declaration)
    (consumer / "ruff.toml").write_text('[lint]\nselect = ["F", "E", "RUF"]\nignore = ["ANN401"]\n')
    result = _run(consumer, shelf)
    assert result.returncode == 0, result.stderr


def test_a_declared_shadow_still_fails_when_the_effective_config_drifts(tmp_path: Path, shelf: Path) -> None:
    consumer = _write(tmp_path / "consumer", _SHELF + '\n[tool.shelf-preset]\nruff-config-shadows = ["ruff.toml"]\n')
    (consumer / "ruff.toml").write_text(_OLD_RULES)
    result = _run(consumer, shelf)
    assert result.returncode == 1
    assert "shadows" not in result.stderr
    assert "missing 'RUF'" in result.stderr


def test_a_ruff_toml_with_no_ruff_block_in_pyproject_is_just_the_config(tmp_path: Path, shelf: Path) -> None:
    consumer = _write(tmp_path / "consumer", '[tool.pyrefly.errors]\ndeprecated = "error"\n')
    (consumer / "ruff.toml").write_text('[lint]\nselect = ["F", "E", "RUF"]\nignore = ["ANN401"]\n')
    result = _run(consumer, shelf)
    assert result.returncode == 0, result.stderr


def test_dot_ruff_toml_wins_over_ruff_toml(tmp_path: Path, shelf: Path) -> None:
    consumer = _write(tmp_path / "consumer", '[tool.pyrefly.errors]\ndeprecated = "error"\n')
    (consumer / "ruff.toml").write_text('[lint]\nselect = ["F", "E", "RUF"]\nignore = ["ANN401"]\n')
    (consumer / ".ruff.toml").write_text(_OLD_RULES)
    result = _run(consumer, shelf)
    assert result.returncode == 1
    assert "missing 'RUF'" in result.stderr


def test_the_packaged_preset_carries_no_shelf_only_path() -> None:
    """A consumer's copy of the preset holds rules, versions and size caps: never `packages/*` or `tools/**` of the shelf's own tree."""
    text = preset.REFERENCE.read_text()
    assert "packages/" not in text
    assert "tools/" not in text
    assert "per-file-ignores" not in text
