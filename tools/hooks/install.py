#!/usr/bin/env python3
"""Install the shelf's commit guard as a git pre-commit hook in a consumer repo.

Fast feedback, not enforcement — enforcement is ``make guard`` in the gate
(``docs/consuming-the-shelf.md`` §2). This hook catches the mistake at commit
time instead of at gate time:

    python /path/to/shelf/tools/hooks/install.py [repo-root]   # default: cwd

Idempotent and marker-guarded: re-running is safe; it refuses to clobber a
foreign pre-commit hook, naming the tool that owns it and that tool's own
extension point.

**Where the hook goes is git's answer, not ours.** The directory comes from
``git rev-parse --git-path hooks``, which honors ``core.hooksPath``. Deriving it
as ``<git-dir>/hooks`` was a real defect: where ``core.hooksPath`` is set — beads,
husky, lefthook — git stops reading ``.git/hooks`` entirely, so the installer
reported success, the file existed, and the hook never ran.

**Success means the hook was observed to block, not that a file was written.**
Those two came apart in exactly the way above, and every cheap check — marker
present, mode bit set, file on disk — passed while a repo sat unguarded.
Verification is read-only: it runs the hook against a throwaway index in a
throwaway object store, so the repo's index, working tree, history, and object
database are untouched.

Exit codes: ``0`` verified live · ``1`` refused, or written but NOT live ·
``2`` could not verify. A check that could not run is never reported as a pass.

**The guarded span is marker-delimited (BEGIN/END), and never ``exec``s.**
Found for real, re-onboarding a2kay with ``beads``: ``bd init`` detects this
guard as a native hook and chains its own pre-commit integration *after* it in
the same file — exactly the intended "guard before ``bd init``" ordering. But
the body used to end in ``exec python3 "$GUARD"``, which REPLACES the shell
process on success — so anything appended after it, including bd's chained
block, was unreachable dead code from the moment it was chained, independent
of any reinstall. The body now runs the guard and exits only on failure,
letting execution fall through to whatever another tool appended. Re-running
the installer replaces only the text between its own BEGIN/END markers,
preserving anything before or after — the same non-clobbering discipline
``beads.py``'s dolt-push chain already applies in the other direction.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

MARKER = "# shelf-guard (no-local-shelf-source)"
_BEGIN = f"{MARKER} BEGIN — managed by the shelf installer; safe to re-run."

# The pre-BEGIN/END format, live only briefly this session before this fix — but already
# committed into at least one real consumer's history (a2kay), so a first re-run there hits it
# for real, not hypothetically. `_OLD_END` was the exec-based template's literal last line;
# without an explicit END marker of its own, it is the only reliable boundary between the old
# span and anything a tool chained after it. Kept only for `_rewritten_hook`'s one-time
# migration path — never written by this version of the installer.
_OLD_BEGIN = f"{MARKER} — managed by the shelf installer; safe to re-run."
_OLD_END = "exit 0   # guard unavailable (shelf not cloned) -> do not block"
_END = f"{MARKER} END"

VERIFIED, REFUSED, COULD_NOT_VERIFY = 0, 1, 2

GUARD_REL = "tools/hooks/forbid-local-shelf-source.py"

# An offending pyproject, staged only into a throwaway index during verification.
_OFFENDER = """\
[project]
name = "shelf-guard-probe"
version = "0.0.0"

[tool.uv.sources]
probe = { path = "../shelf/packages/probe", editable = true }
"""

# Tools that manage a pre-commit hook, and where each one actually wants an
# addition. Hand-editing a generated hook is advice that breaks on the owner's
# next regeneration, so name the owner's own extension point instead.
_MANAGERS: tuple[tuple[str, str, str], ...] = (
    (
        "BEGIN BEADS INTEGRATION",
        "beads",
        "append your addition AFTER the '--- END BEADS INTEGRATION ---' marker\n"
        "    (inside it, a future `bd` upgrade will clobber the addition or trip its drift check)",
    ),
    (
        "pre-commit.com",
        "the pre-commit framework",
        "no manual chaining needed — the shelf already ships this hook:\n"
        "      - repo: https://github.com/yoselabs/shelf\n"
        "        rev: <a shelf commit or tag>\n"
        "        hooks: [{ id: no-local-shelf-source }]",
    ),
    (
        "husky",
        "husky",
        "add a new file under your husky hooks directory rather than editing this one",
    ),
    (
        "lefthook",
        "lefthook",
        "add a `pre-commit` command entry to lefthook.yml rather than editing this one",
    ),
)

# The guarded span only — no shebang, no trailing `exit 0`. `exit 0` at the end
# would terminate the script before reaching anything another tool appends
# after this span, same failure as `exec` would have been.
GUARDED_SPAN = f"""{_BEGIN}
SHELF="${{SHELF_HOME:-../shelf}}"
[ -d "$SHELF" ] || SHELF="$HOME/Workspaces/shelf"
GUARD="$SHELF/tools/hooks/forbid-local-shelf-source.py"
if [ -f "$GUARD" ]; then
  python3 "$GUARD" || exit 1
fi
{_END}
"""

HOOK = f"#!/bin/sh\n{GUARDED_SPAN}"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)


def _hooks_dir(repo: Path) -> Path | None:
    """Where git will actually look for hooks, asked of git rather than assumed.

    `--git-path hooks` resolves `core.hooksPath` when set and falls back to
    `.git/hooks` when it is not. Re-deriving that ourselves would re-implement
    git's own resolution and drift from it — which is the defect this replaced.
    """
    result = _git(repo, "rev-parse", "--git-path", "hooks")
    if result.returncode != 0:
        return None
    path = Path(result.stdout.strip())
    return path if path.is_absolute() else repo / path


def _identify_manager(body: str) -> tuple[str, str] | None:
    lowered = body.lower()
    for needle, name, advice in _MANAGERS:
        if needle.lower() in lowered:
            return name, advice
    return None


def _resolve_guard(repo: Path) -> Path | None:
    """Mirror HOOK's own shelf resolution, so we know whether it can find the guard."""
    candidates = []
    if os.environ.get("SHELF_HOME"):
        candidates.append(Path(os.environ["SHELF_HOME"]))
    candidates.append(repo / ".." / "shelf")
    candidates.append(Path(os.environ.get("HOME", "~")).expanduser() / "Workspaces" / "shelf")
    for base in candidates:
        guard = base / GUARD_REL
        if guard.is_file():
            return guard
    return None


def _verify_live(repo: Path, hook: Path) -> tuple[bool, str]:
    """Run the hook against a throwaway index and require it to refuse.

    Read-only by construction: `GIT_INDEX_FILE` and `GIT_OBJECT_DIRECTORY` point at
    temporary locations, so the probe blob and the staged offender exist only there.
    The repo's index, working tree, history, and object database are untouched — a
    check that quietly mutated the thing it inspects would be its own defect.

    The hook is executed directly rather than through `git hook run`, which would
    fire every other tool's pre-commit hook too and trigger their side effects.
    """
    with tempfile.TemporaryDirectory() as tmp:
        objects = Path(tmp) / "objects"
        objects.mkdir()
        env = {
            **os.environ,
            "GIT_INDEX_FILE": str(Path(tmp) / "index"),
            "GIT_OBJECT_DIRECTORY": str(objects),
        }
        blob = subprocess.run(
            ["git", "-C", str(repo), "hash-object", "-w", "--stdin"],
            input=_OFFENDER,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        if blob.returncode != 0:
            return False, "could not stage a probe"
        staged = subprocess.run(
            ["git", "-C", str(repo), "update-index", "--add", "--cacheinfo", f"100644,{blob.stdout.strip()},pyproject.toml"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        if staged.returncode != 0:
            return False, "could not stage a probe"
        try:
            ran = subprocess.run([str(hook)], cwd=repo, capture_output=True, text=True, check=False, env=env)
        except OSError as exc:  # not executable, bad interpreter, …
            return False, f"the hook could not be executed ({exc.strerror})"
    if ran.returncode == 0:
        return False, "the hook ran but did not refuse an offending change"
    return True, ""


def _rewritten_hook(existing: str | None) -> str:
    """The hook's new content: fresh (`HOOK`) if absent, `GUARDED_SPAN` spliced back in otherwise.

    Preserves everything another tool put before or after it, since re-running
    must never clobber a chain another tool built on top of a previously
    installed guard. Also migrates the pre-BEGIN/END format in place (see
    `_OLD_BEGIN`/`_OLD_END`) rather than falling back to a full overwrite,
    which would silently repeat the exact loss this format change fixed for
    anyone whose hook was written before it.
    """
    if existing is None:
        return HOOK
    start, end, end_len = existing.find(_BEGIN), existing.find(_END), len(_END)
    if start == -1 or end == -1:
        start, end, end_len = existing.find(_OLD_BEGIN), existing.find(_OLD_END), len(_OLD_END)
    if start == -1 or end == -1:
        return HOOK
    return existing[:start] + GUARDED_SPAN + existing[end + end_len :].lstrip("\n")


def main() -> int:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()

    hooks = _hooks_dir(repo)
    if hooks is None:
        print(f"✖ not a git repository: {repo}", file=sys.stderr)
        return REFUSED

    if (repo / ".pre-commit-config.yaml").exists() and _git(repo, "config", "core.hooksPath").returncode == 0:
        print("⚠ this repo has BOTH a .pre-commit-config.yaml and core.hooksPath set.", file=sys.stderr)
        print(f"  Only one tool can own the hook slot; git currently reads {hooks}.", file=sys.stderr)
        print("  Do NOT run `git config --unset-all core.hooksPath` (the hint pre-commit", file=sys.stderr)
        print("  prints) without checking what owns that path — it revives pre-commit and", file=sys.stderr)
        print("  silently disables every hook there, beads' Dolt sync included.", file=sys.stderr)

    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-commit"

    if hook.exists() and MARKER not in hook.read_text():
        owner = _identify_manager(hook.read_text())
        print(f"✖ {hook} already exists and is not shelf-managed — will not clobber.", file=sys.stderr)
        if owner is not None:
            name, advice = owner
            print(f"  It is managed by {name}: {advice}", file=sys.stderr)
        else:
            print("  Add this line to it (or use the pre-commit framework):", file=sys.stderr)
            print('    python3 "$SHELF_HOME/tools/hooks/forbid-local-shelf-source.py" || exit 1', file=sys.stderr)
        return REFUSED

    hook.write_text(_rewritten_hook(hook.read_text() if hook.exists() else None))
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    if _resolve_guard(repo) is None:
        print(f"⚠ shelf commit guard written to {hook}, but NOT VERIFIED.")
        print("  No shelf clone was found, so the hook's own fail-open branch is active:")
        print("  it will exit 0 rather than block. Set $SHELF_HOME (or clone the shelf to")
        print("  ~/Workspaces/shelf) and re-run to verify. Unverified is not installed.")
        return COULD_NOT_VERIFY

    live, why = _verify_live(repo, hook)
    if not live:
        print(f"✖ shelf commit guard written to {hook}, but it is NOT live — {why}.", file=sys.stderr)
        print(f"  git reads hooks from: {hooks}", file=sys.stderr)
        print("  A hook that exists is not a hook that runs; treat this repo as unguarded.", file=sys.stderr)
        return REFUSED

    print(f"✔ shelf commit guard installed at {hook} — verified live (it refused a probe).")
    return VERIFIED


if __name__ == "__main__":
    raise SystemExit(main())
