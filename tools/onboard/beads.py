"""The `beads` operation: `bd init` without bd's hooks, the strict settings with readback, quiet sessions.

- **No hooks from bd.** `bd init --skip-hooks`: bd's events run from prek's config (the `hooks`
  operation). bd's own injection made a failing check stop blocking commits in other managers' hook
  files, and pointed `core.hooksPath` at an absolute path a fresh clone does not have.
- **Strict settings, written to the file, read back by the audit.** The blueprint's strict set
  (blueprint/concerns/backlog.py STRICT) is written into `.beads/config.yaml` itself: `bd config set`
  stores keys it does not own in bd's database, where a fresh clone never sees them (a2peer: `import.auto`
  came back true). The proof is the audit's own `backlog.strict-config` row, not a set's success message.
- **Quiet, primed sessions.** `.claude/settings.json` gets `BD_DISABLE_METRICS=1` (bd reads
  `metrics.disabled` only from the user config, so the repo sets it per session) and the two session
  hooks: SessionStart runs `bd prime`, Stop lists beads left in progress. Merged, never overwritten.
- **bd's root lock ignored.** bd 1.3 writes `.beads.gate.lock` beside `.beads/`; `.gitignore` gets a line for it.
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


_INDENT = 4  # bd writes nested keys with four spaces


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_content(line: str) -> bool:
    return bool(line.strip()) and not line.lstrip().startswith("#")


def _find(lines: list[str], key: str, lo: int, hi: int, indent: int) -> int | None:
    return next(
        (i for i in range(lo, hi) if _is_content(lines[i]) and _indent(lines[i]) == indent and lines[i].lstrip().startswith(f"{key}:")),
        None,
    )


def _block_end(lines: list[str], at: int, indent: int) -> int:
    """One past the last line nested under `lines[at]`; trailing comments and blanks belong to what follows."""
    last = at
    for j in range(at + 1, len(lines)):
        if not _is_content(lines[j]):
            continue
        if _indent(lines[j]) <= indent:
            break
        last = j
    return last + 1


def _set_key(lines: list[str], path: list[str], value: str) -> None:
    lo, hi, indent = 0, len(lines), 0
    for depth, key in enumerate(path):
        at = _find(lines, key, lo, hi, indent)
        if depth == len(path) - 1:
            line = f"{' ' * indent}{key}: {value}"
            if at is None:
                lines.insert(hi, line)
            else:
                lines[at] = line
            return
        if at is None:
            nested = [f"{' ' * (indent + _INDENT * n)}{k}:" for n, k in enumerate(path[depth:-1])]
            nested.append(f"{' ' * (indent + _INDENT * (len(path) - 1 - depth))}{path[-1]}: {value}")
            lines[hi:hi] = nested
            return
        if lines[at].split(":", 1)[1].split("#", 1)[0].strip():
            msg = f"{'.'.join(path[: depth + 1])} is not a block in config.yaml; edit it by hand"
            raise ValueError(msg)
        end = _block_end(lines, at, indent)
        children = [i for i in range(at + 1, end) if _is_content(lines[i])]
        lo, hi, indent = at + 1, end, _indent(lines[children[0]]) if children else indent + _INDENT


def set_yaml_keys(text: str, values: dict[str, str]) -> str:
    """`text` with each dotted key (`export.auto`) set to its value, as nested block YAML; comments and other keys stay.

    Why not a YAML library: bd's config.yaml is a commented template, and a round trip through a parser drops the comments.
    """
    lines = text.splitlines()
    for dotted, value in values.items():
        _set_key(lines, dotted.split("."), value)
    return "\n".join(lines) + "\n"


def _write_strict(repo: Path, strict: dict[str, str]) -> Result | None:
    """Write the strict set into .beads/config.yaml; None on success."""
    path = repo / ".beads" / "config.yaml"
    if not path.is_file():
        return Result(Outcome.FAILED, verified=False, message="bd init left no .beads/config.yaml")
    try:
        path.write_text(set_yaml_keys(path.read_text(), strict))
    except ValueError as exc:
        return Result(Outcome.FAILED, verified=False, message=str(exc))
    return None


def _audit_strict(repo: Path) -> str | None:
    """Evidence of what the blueprint's `backlog.strict-config` still objects to, or None when it passes."""
    if str(_BLUEPRINT_SRC) not in sys.path:
        sys.path.insert(0, str(_BLUEPRINT_SRC))
    from blueprint.model import Verdict  # noqa: PLC0415 -- resolved from the shelf clone at run time
    from blueprint.runner import run  # noqa: PLC0415 -- same

    rows = {r.id: r for r in run(repo, concern="backlog", audit=True).rows}
    row = rows.get("backlog.strict-config")
    if row is None:
        return "backlog.strict-config did not run (no tracker detected)"
    return None if row.verdict is Verdict.PASSING else row.evidence


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


_ROOT_LOCK = ".beads.gate.lock"


def _ignore_root_lock(repo: Path) -> None:
    """bd 1.3 writes .beads.gate.lock at the repo root on every run: git-ignore it (blueprint's backlog.lock-ignored)."""
    ignored = subprocess.run(["git", "check-ignore", "-q", "--no-index", _ROOT_LOCK], cwd=repo, check=False).returncode == 0
    if not ignored:
        gitignore = repo / ".gitignore"
        text = gitignore.read_text() if gitignore.exists() else ""
        gitignore.write_text(text + ("" if not text or text.endswith("\n") else "\n") + f"{_ROOT_LOCK}*\n")


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
        if (failed := _write_strict(self.repo, strict)) is not None:
            return failed
        if (wrong := _audit_strict(self.repo)) is not None:
            return Result(Outcome.FAILED, verified=False, message=f"config readback mismatch: {wrong}")

        if (failed := _settings(self.repo)) is not None:
            return failed
        _ignore_root_lock(self.repo)
        return Result(
            Outcome.APPLIED,
            verified=True,
            message=f"{len(strict)} strict settings in .beads/config.yaml, read back by the audit; session env and hooks set",
        )
