"""Every script run directly is a command: `--help` prints its usage and exits 0, an unknown flag exits 2 (ADR 0025)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = [
    ".agents/skills/onboard-consumer/scripts/onboard.py",
    "packages/blueprint/src/blueprint/recipes/check_coverage.py",
    "packages/blueprint/src/blueprint/recipes/check_dockerfile_pins.py",
    "packages/blueprint/src/blueprint/recipes/check_godot.py",
    "packages/blueprint/src/blueprint/recipes/unity_integrity.py",
    "packages/convert-md/bench/engines/run_docling.py",
    "packages/convert-md/bench/engines/run_mammoth.py",
    "packages/convert-md/bench/engines/run_marker.py",
    "packages/convert-md/bench/engines/run_markitdown.py",
    "packages/convert-md/bench/engines/run_pandoc.py",
    "packages/convert-md/bench/engines/run_pymupdf4llm.py",
    "packages/convert-md/bench/engines/run_unstructured.py",
    "packages/convert-md/bench/run_bench.py",
    "tools/affected.py",
    "tools/catalog.py",
    "tools/changed.py",
    "tools/hooks/forbid-local-shelf-source.py",
    "tools/preset_drift.py",
]


def _run(script: str, flag: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", str(_ROOT / script), flag], capture_output=True, text=True, timeout=30, cwd=cwd, check=False
    )


@pytest.mark.parametrize("script", _SCRIPTS)
def test_help_prints_usage_and_exits_zero(script: str, tmp_path: Path) -> None:
    done = _run(script, "--help", tmp_path)
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("usage:")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("script", _SCRIPTS)
def test_an_unknown_flag_is_refused_with_exit_two(script: str, tmp_path: Path) -> None:
    assert _run(script, "--no-such-flag", tmp_path).returncode == 2
