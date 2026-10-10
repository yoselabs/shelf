"""The `beads` operation: `bd init` without bd's hooks, the strict settings with readback, quiet sessions.

- **No hooks from bd.** `bd init --skip-hooks`: bd's events run from prek's config (the `hooks`
  operation). bd's own injection made a failing check stop blocking commits in other managers' hook
  files, and pointed `core.hooksPath` at an absolute path a fresh clone does not have.
- **Strict settings, read back.** The blueprint's strict set (blueprint/concerns/backlog.py STRICT)
  is `set` then `get`; `.beads/config.yaml` is tracked and a checkout can revert it silently, so the
  readback is the proof, not the set's success message.
- **Quiet, primed sessions.** `.claude/settings.json` gets `BD_DISABLE_METRICS=1` (bd reads
  `metrics.disabled` only from the user config, so the repo sets it per session) and the two session
  hooks: SessionStart runs `bd prime`, Stop lists beads left in progress. Merged, never overwritten.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .operations import Outcome, Result

# The blueprint's strict set (packages/blueprint/src/blueprint/concerns/backlog.py STRICT), read from
# the shelf clone this script runs from, so onboarding and the audit can never disagree.
_BLUEPRINT_SRC = Path(__file__).resolve().parent.parent.parent / "packages" / "blueprint" / "src"
_METRICS_ENV = "BD_DISABLE_METRICS"
_SESSION_HOOKS = {
    "SessionStart": "bd prime --hook-json",
    # Lists beads left in progress so no session ends with work silently open.
    "Stop": (
        "(bd list --status in_progress --json 2>/dev/null || echo '[]') | jq -c "
        '\'if length > 0 then {systemMessage: ("beads left in_progress: " + ([.[] | .id] | join(", ")))} else empty end\''
    ),
}


def _strict() -> dict[str, str]:
    if str(_BLUEPRINT_SRC) not in sys.path:
        sys.path.insert(0, str(_BLUEPRINT_SRC))
    from blueprint.concerns.backlog import STRICT  # noqa: PLC0415 -- resolved from the shelf clone at run time

    return dict(STRICT)


def _bd(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bd", *args], cwd=repo, capture_output=True, text=True, check=False)


def _settings(repo: Path) -> Result | None:
    """Merge the metrics env and the two session hooks into .claude/settings.json; None on success."""
    path = repo / ".claude" / "settings.json"
    try:
        data: dict[str, Any] = json.loads(path.read_text()) if path.exists() else {}
    except json.JSONDecodeError as exc:
        return Result(Outcome.FAILED, verified=False, message=f"{path} is not valid JSON: {exc}")
    data.setdefault("env", {})[_METRICS_ENV] = "1"
    hooks: dict[str, list[Any]] = data.setdefault("hooks", {})
    for event, command in _SESSION_HOOKS.items():
        needle = "bd prime" if event == "SessionStart" else "in_progress"
        if needle not in json.dumps(hooks.get(event, [])):
            hooks.setdefault(event, []).append({"hooks": [{"type": "command", "command": command}]})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return None


@dataclass
class BeadsOperation:
    """`bd init --skip-hooks`, the strict settings with readback, and the session settings."""

    repo: Path
    name: str = "beads"
    requires: tuple[str, ...] = ()

    def run(self, _results: dict[str, Result]) -> Result:
        """Init (if needed), set and read back the strict set, merge the session settings."""
        if shutil.which("bd") is None:
            return Result(Outcome.COULD_NOT_APPLY, verified=False, message="bd is not installed")

        if not (self.repo / ".beads").is_dir():
            init = _bd(self.repo, "init", "--non-interactive", "--role", "maintainer", "--skip-hooks")
            combined = init.stdout + init.stderr
            if init.returncode != 0 and "already initialized" not in combined:
                return Result(Outcome.FAILED, verified=False, message=combined.strip())

        strict = _strict()
        for key, value in strict.items():
            _bd(self.repo, "config", "set", key, value)
        readback = {key: _bd(self.repo, "config", "get", key).stdout.strip() for key in strict}
        wrong = {k: v for k, v in readback.items() if v != strict[k]}
        if wrong:
            return Result(Outcome.FAILED, verified=False, message=f"config readback mismatch: {wrong}")

        if (failed := _settings(self.repo)) is not None:
            return failed
        return Result(Outcome.APPLIED, verified=True, message=f"{len(strict)} strict settings read back; session env and hooks set")
