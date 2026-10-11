"""A hermetic PATH for tests that run real tools (bd, just, prek, git) under a scratch HOME.

A tool found through a mise shim cannot run once HOME points at a scratch dir: the shim reads the
version from the user's mise config there. So each tool resolves to its real binary first (`mise
which`), and only those folders go on PATH, ahead of the system ones.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_TOOLS = ("bd", "just", "prek", "git", "uv")
_SYSTEM = ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin")


def _real(tool: str) -> Path | None:
    found = shutil.which(tool)
    if found is None:
        return None
    if Path(found).resolve().name == "mise" and shutil.which("mise"):
        done = subprocess.run(["mise", "which", tool], capture_output=True, text=True, check=False)
        return Path(done.stdout.strip()) if done.returncode == 0 and done.stdout.strip() else None
    return Path(found)


def hermetic_path() -> str:
    """This interpreter's folder, each real tool's folder, then the system folders."""
    dirs = [str(Path(sys.executable).parent)]
    dirs += [str(p.parent) for t in _TOOLS if (p := _real(t)) is not None]
    dirs += list(_SYSTEM)
    return ":".join(dict.fromkeys(dirs))


def has(tool: str) -> bool:
    """Whether `tool` resolves to a runnable binary (a dangling mise shim does not)."""
    return _real(tool) is not None
