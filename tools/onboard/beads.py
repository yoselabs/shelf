"""The `beads` operation — `bd init`, config with readback, `bd dolt push` chained onto the `pre-push` hook.

Encodes `docs/runbooks/adopt-beads.md` §1.2 and §2.2:

- **Config readback, not trust.** `bd config set`'s success message reports intent, not surviving
  state — `.beads/config.yaml` is a *tracked* file an ordinary `git checkout`/`reset` can silently
  revert underneath it (shelf hit this for real, 2026-08-12). So every `set` here is followed by a
  `get` and the Result is FAILED if they disagree.
- **Requires `guard`.** `bd init` seizes `core.hooksPath` when the repo has no native hook to chain
  into yet (`fix-guard-hookspath-resolution` landmine 1) — the guard must already be installed and
  verified so it ends up wherever `bd init` leaves hook resolution, not the stale `<git-dir>/hooks`
  path a hardcoded installer would have used.
- **Dolt-push chained outside bd's own markers.** `bd hooks run pre-push` does not push
  `refs/dolt/data` — a plain `git push` and `bd dolt push` are two independent remote syncs. The
  fix is appended strictly after bd's own `--- END BEADS INTEGRATION ... ---` marker, never inside
  it, because a future `bd` upgrade rewrites everything between its own markers.

Verification here is partial and says so: actually invoking `bd dolt push` would require a real
Dolt remote and touch the network, which an operation must not do as a side effect of onboarding.
`sh -n` on the hook file is a real (if weaker) exercise of the appended shell, not a marker check —
consistent with D3.3's ban on trusting an artifact, short of a live network call this operation has
no business making.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .operations import Outcome, Result

_DOLT_PUSH_MARKER = "# shelf-onboarding: bd dolt push chain (not beads-managed)"
_END_BEADS_RE = re.compile(r"^# --- END BEADS INTEGRATION.*---\s*$", re.MULTILINE)

_DOLT_PUSH_BLOCK = f"""{_DOLT_PUSH_MARKER}
# `bd hooks run pre-push` above does NOT push the Dolt data ref (refs/dolt/data) --
# git push and bd dolt push are two separate remote syncs. Chain it here so a plain
# `git push` can never leave the beads queue behind on the remote. Non-fatal: a
# network hiccup on the Dolt push must not block the code push.
if command -v bd >/dev/null 2>&1; then
  bd dolt push || echo >&2 "beads: 'bd dolt push' failed -- beads queue not synced to remote, push it manually"
fi
"""

_CONFIG_KEYS = ("export.auto", "export.git-add")


def _bd(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bd", *args], cwd=repo, capture_output=True, text=True, check=False)


def _hooks_dir(repo: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-path", "hooks"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    p = Path(result.stdout.strip())
    return p if p.is_absolute() else repo / p


def _chain_dolt_push(pre_push: Path) -> Result:
    if not pre_push.exists():
        return Result(Outcome.FAILED, verified=False, message=f"{pre_push} missing after `bd init` — bd did not install its own hook")

    body = pre_push.read_text()
    if _DOLT_PUSH_MARKER not in body:
        match = _END_BEADS_RE.search(body)
        if match is None:
            return Result(Outcome.FAILED, verified=False, message=f"{pre_push} has no beads END marker to append after")
        body = body[: match.end()] + "\n" + _DOLT_PUSH_BLOCK + body[match.end() :]
        pre_push.write_text(body)

    check = subprocess.run(["sh", "-n", str(pre_push)], capture_output=True, text=True, check=False)
    if check.returncode != 0:
        return Result(Outcome.FAILED, verified=False, message=f"{pre_push} fails shell syntax check: {check.stderr.strip()}")
    return Result(Outcome.APPLIED, verified=True, message=f"dolt-push chained onto {pre_push}")


@dataclass
class BeadsOperation:
    """`bd init` + config-set-with-readback + the dolt-push hook chain, in one operation."""

    repo: Path
    name: str = "beads"
    requires: tuple[str, ...] = ("guard",)

    def run(self, _results: dict[str, Result]) -> Result:
        """Init (if needed), set+readback config, chain the dolt-push hook."""
        if shutil.which("bd") is None:
            return Result(Outcome.COULD_NOT_APPLY, verified=False, message="bd is not installed")

        if not (self.repo / ".beads").is_dir():
            init = _bd(self.repo, "init", "--non-interactive", "--role", "maintainer")
            combined = init.stdout + init.stderr
            if init.returncode != 0 and "already initialized" not in combined:
                return Result(Outcome.FAILED, verified=False, message=combined.strip())

        for key in _CONFIG_KEYS:
            _bd(self.repo, "config", "set", key, "true")

        readback = {key: _bd(self.repo, "config", "get", key).stdout.strip() for key in _CONFIG_KEYS}
        if any(value != "true" for value in readback.values()):
            return Result(Outcome.FAILED, verified=False, message=f"config readback mismatch: {readback}")

        hooks = _hooks_dir(self.repo)
        if hooks is None:
            return Result(Outcome.FAILED, verified=False, message=f"{self.repo} is not a git repository")

        return _chain_dolt_push(hooks / "pre-push")
