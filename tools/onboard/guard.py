"""The `guard` operation — installs and verifies the commit guard.

Wraps `tools/hooks/install.py` (`fix-guard-hookspath-resolution` / shelf-efh) as
an `Operation`. Does NOT reimplement it: `install.py` already satisfies D3 on
its own (idempotent, verifies liveness against a throwaway index, three exit
codes, non-destructive — see `tests/test_hook_installer.py`), so this module's
only job is running it as a subprocess and translating its exit code.

Subprocess, not import: `install.py` is itself a standalone CLI, run in a
consumer repo that has no dependency on shelf's own Python environment. Calling
it the same way a human or `make bootstrap` would keeps this operation exactly
as trustworthy as the CLI it wraps.

No `requires` — in D1's ordering, `guard` runs first; `beads` depends on it.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .operations import Outcome, Result

_INSTALL = Path(__file__).resolve().parent.parent / "hooks" / "install.py"

_EXIT_TO_OUTCOME = {
    0: (Outcome.APPLIED, True),  # VERIFIED
    1: (Outcome.FAILED, False),  # REFUSED
    2: (Outcome.COULD_NOT_APPLY, False),  # COULD_NOT_VERIFY
}


@dataclass
class GuardOperation:
    """Runs `tools/hooks/install.py` against `repo` and reports its verdict."""

    repo: Path
    name: str = "guard"
    requires: tuple[str, ...] = ()

    def run(self, _results: dict[str, Result]) -> Result:
        """Run `install.py` against `self.repo` and translate its exit code."""
        proc = subprocess.run(
            [sys.executable, str(_INSTALL), str(self.repo)],
            capture_output=True,
            text=True,
            check=False,
        )
        outcome, verified = _EXIT_TO_OUTCOME.get(proc.returncode, (Outcome.COULD_NOT_APPLY, False))
        message = (proc.stdout + proc.stderr).strip()
        return Result(outcome, verified=verified, message=message)
