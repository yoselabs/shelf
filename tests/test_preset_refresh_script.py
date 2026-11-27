"""tools/preset_refresh/preset_refresh.py (shelf-only) answers --help and changes nothing."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_help_exits_zero_and_writes_nothing() -> None:
    target = ROOT / "packages" / "blueprint" / "src" / "blueprint" / "preset.toml"
    before = target.read_bytes()
    script = str(ROOT / "tools" / "preset_refresh" / "preset_refresh.py")
    done = subprocess.run([sys.executable, "-I", script, "--help"], capture_output=True, text=True, check=False)
    assert done.returncode == 0
    assert "preset" in done.stdout
    assert target.read_bytes() == before
