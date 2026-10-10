"""The `linter-preset` operation (python+uv only) — copies missing tables/targets
from shelf's own `pyproject.toml`/`Makefile`, never touching what's already there.
"""

from __future__ import annotations

import subprocess
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


def test_an_unrelated_owned_bootstrap_target_is_not_aliased_by_bootstrap_verify(repo: Path) -> None:
    """Found against a real consumer (a2kay): it already had its own `bootstrap:` target (a
    common Make name, unrelated to shelf onboarding). `bootstrap` is correctly left alone as
    owned -- but `bootstrap-verify: bootstrap` must not be copied either, since on its own it
    would silently alias to the consumer's unrelated target rather than shelf's onboarding
    script."""
    (repo / "pyproject.toml").write_text('[project]\nname = "consumer"\nversion = "0.1.0"\n')
    (repo / "Makefile").write_text("bootstrap:\n\techo set up my own dev env, nothing to do with the shelf\n")

    result = LinterPresetOperation(repo).run({})

    assert result.outcome == Outcome.APPLIED, result.message
    make_text = (repo / "Makefile").read_text()
    assert "echo set up my own dev env" in make_text, "the consumer's own bootstrap target was overwritten"
    assert "bootstrap-verify" not in make_text, "bootstrap-verify would alias to the consumer's unrelated bootstrap target"
    assert "guard:" in make_text, "unrelated targets must still be copied"


def test_creates_a_makefile_from_scratch_when_absent(repo: Path) -> None:
    (repo / "pyproject.toml").write_text('[project]\nname = "consumer"\nversion = "0.1.0"\n')

    result = LinterPresetOperation(repo).run({})

    assert result.outcome == Outcome.APPLIED, result.message
    make_text = (repo / "Makefile").read_text()
    for target in (
        "check:",
        "guard:",
        "bootstrap:",
        "bootstrap-verify:",
        "lint:",
        "format:",
        "typecheck:",
        "spell:",
        "deps:",
        "test:",
    ):
        assert target in make_text


# ── shelf-4mz: the copied gate must RUN, not merely exist ─────────────────────
# Reproduced 2026-10-10: a fresh repo onboarded with every operation verified=True,
# then `make check` stopped at once on a missing `preset` target; `deps` looped over
# the shelf's own packages/*; and no pyrefly table meant `make typecheck` ran lax.


def _bare(repo: Path) -> None:
    (repo / "pyproject.toml").write_text('[project]\nname = "consumer"\nversion = "0.1.0"\n')


def _make_dry_run(repo: Path, target: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["make", "-n", target], cwd=repo, capture_output=True, text=True, check=False)


def test_a_fresh_repo_gets_a_gate_whose_every_target_resolves(repo: Path) -> None:
    _bare(repo)

    result = LinterPresetOperation(repo).run({})

    assert result.outcome == Outcome.APPLIED, result.message
    dry = _make_dry_run(repo, "check")
    assert dry.returncode == 0, dry.stderr


def test_pyrefly_is_strict_and_carries_none_of_the_shelfs_own_paths(repo: Path) -> None:
    _bare(repo)

    LinterPresetOperation(repo).run({})

    pyrefly = tomllib.loads((repo / "pyproject.toml").read_text())["tool"]["pyrefly"]
    shelf = tomllib.loads((_ROOT / "pyproject.toml").read_text())["tool"]["pyrefly"]
    assert pyrefly["preset"] == "strict"
    assert pyrefly["errors"] == shelf["errors"], "preset drift compares this axis; it must match the shelf"
    assert "project-includes" not in pyrefly
    assert "project-excludes" not in pyrefly
    assert "search-path" not in pyrefly
    assert [sub["matches"] for sub in pyrefly["sub-config"]] == ["tests/**"]


def test_pytest_gets_strict_markers_and_none_of_the_shelfs_testpaths(repo: Path) -> None:
    _bare(repo)

    LinterPresetOperation(repo).run({})

    pytest_cfg = tomllib.loads((repo / "pyproject.toml").read_text())["tool"]["pytest"]["ini_options"]
    assert "--strict-markers" in pytest_cfg["addopts"]
    assert "testpaths" not in pytest_cfg


def test_deps_checks_the_consumer_itself_not_the_shelfs_packages(repo: Path) -> None:
    _bare(repo)

    LinterPresetOperation(repo).run({})

    deps = _make_dry_run(repo, "deps")
    assert deps.returncode == 0, deps.stderr
    assert "packages/" not in deps.stdout
    assert "deptry ." in deps.stdout


def test_a_copied_gate_that_names_a_missing_target_is_a_failure(repo: Path) -> None:
    _bare(repo)
    (repo / "Makefile").write_text("check: guard lint not-a-target\n")

    result = LinterPresetOperation(repo).run({})

    assert result.outcome == Outcome.FAILED
    assert "not-a-target" in result.message


def test_a_freshly_onboarded_repo_passes_preset_drift(repo: Path) -> None:
    _bare(repo)

    LinterPresetOperation(repo).run({})

    drift = subprocess.run(
        [sys.executable, str(_ROOT / "tools" / "preset_drift.py"), "--repo", str(repo), "--shelf-home", str(_ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert drift.returncode == 0, drift.stderr
