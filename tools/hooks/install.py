#!/usr/bin/env python3
"""Install the shelf's commit hooks — the source guard and the linter — in a consumer repo.

Fast feedback, not enforcement — enforcement is ``make guard`` in the gate
(``docs/consuming-the-shelf.md`` §2). This hook catches the mistake at commit
time instead of at gate time:

    python /path/to/shelf/tools/hooks/install.py [repo-root]   # default: cwd

Two independent marker-delimited spans go into the same ``pre-commit`` file:

``shelf-guard``   refuses a committed local shelf source. Verified LIVE — it is
                  run against a throwaway index and must refuse an offender.
``shelf-lint``    runs ``ruff check`` and ``ruff format --check`` on the staged
                  Python files, and the preset-drift check when ``pyproject.toml``
                  is staged. Reported as installed with ruff RESOLVED, which is a
                  weaker claim than the guard's and is made in those words.

The linter span reads the **working tree** for the staged paths, not the staged
content — so a partially staged file is linted whole. That is the usual shape and
the honest limitation: the hook is fast feedback, `make check` is the enforcement
(`docs/consuming-the-shelf.md` §2). It fails OPEN when ruff cannot be found,
loudly, because a machine without ruff must still be able to commit.

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

_LINT_MARKER = "# shelf-lint (ruff + preset drift)"
_LINT_BEGIN = f"{_LINT_MARKER} BEGIN — managed by the shelf installer; safe to re-run."
_LINT_END = f"{_LINT_MARKER} END"

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

# Ruff over the staged Python files, plus the preset-drift check when the config
# itself is staged. Notes on the shape, since each line is answering something:
#
#   -z into a file    a path with a space — or a newline — is still one path, and the
#                     list is needed twice, so it is materialized once rather than
#                     re-derived (and re-raced against a concurrent `git add`).
#   --force-exclude   without it ruff lints a file its own `exclude` covers: naming a
#                     path explicitly normally overrides exclusion, and this hook names
#                     every path explicitly.
#   fail open         a machine without ruff must still be able to commit. `make lint`
#                     is the enforcement; this is fast feedback.
LINT_SPAN = f"""{_LINT_BEGIN}
_shelf_lint_staged=$(mktemp)
trap 'rm -f "$_shelf_lint_staged"' EXIT
git diff --cached --name-only --diff-filter=ACM -z -- '*.py' > "$_shelf_lint_staged"
if [ -s "$_shelf_lint_staged" ]; then
  _ruff=""
  for _candidate in "./.venv/bin/ruff" "ruff"; do
    if command -v "$_candidate" >/dev/null 2>&1; then _ruff="$_candidate"; break; fi
  done
  if [ -z "$_ruff" ]; then
    echo "shelf-lint: ruff not found (no ./.venv/bin/ruff, none on PATH) -- SKIPPED, not a pass" >&2
  else
    xargs -0 "$_ruff" check --force-exclude < "$_shelf_lint_staged" || exit 1
    xargs -0 "$_ruff" format --check --force-exclude < "$_shelf_lint_staged" || exit 1
  fi
fi
if git diff --cached --name-only --diff-filter=ACM | grep -qx 'pyproject.toml'; then
  SHELF="${{SHELF_HOME:-../shelf}}"
  [ -d "$SHELF" ] || SHELF="$HOME/Workspaces/shelf"
  if [ -f "$SHELF/tools/preset_drift.py" ]; then
    python3 "$SHELF/tools/preset_drift.py" --repo . || exit 1
  fi
fi
{_LINT_END}
"""

HOOK = f"#!/bin/sh\n{GUARDED_SPAN}\n{LINT_SPAN}"


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


def _splice(body: str, begin: str, end: str, span: str, end_len: int | None = None) -> str | None:
    """Replace the `begin`..`end` span in `body`, or `None` when it is not there.

    Everything before and after the span is preserved: re-running must never clobber
    a chain another tool built around a previously installed span.
    """
    start, stop = body.find(begin), body.find(end)
    if start == -1 or stop == -1:
        return None
    tail = body[stop + (end_len if end_len is not None else len(end)) :].lstrip("\n")
    # Exactly one blank line before whatever follows — the same separator a fresh
    # `HOOK` uses, so splicing a hook is byte-identical to writing one and a reinstall
    # is genuinely idempotent rather than off by a newline each time.
    return body[:start] + span + (f"\n{tail}" if tail else "")


def _rewritten_hook(existing: str | None) -> str:
    """The hook's new content: fresh (`HOOK`) if absent, each span spliced back in otherwise.

    The two spans are independent. A hook written before the linter span existed has
    the guard's markers and not the linter's, so the linter is *appended* rather than
    the whole file overwritten — overwriting would drop whatever another tool chained
    on, which is the loss the BEGIN/END format was introduced to stop.

    Also migrates the pre-BEGIN/END guard format in place (see `_OLD_BEGIN`/`_OLD_END`).
    """
    if existing is None:
        return HOOK

    spliced = _splice(existing, _BEGIN, _END, GUARDED_SPAN)
    if spliced is None:
        spliced = _splice(existing, _OLD_BEGIN, _OLD_END, GUARDED_SPAN, end_len=len(_OLD_END))
    if spliced is None:
        return HOOK

    relinted = _splice(spliced, _LINT_BEGIN, _LINT_END, LINT_SPAN)
    if relinted is not None:
        return relinted
    return f"{spliced.rstrip(chr(10))}\n\n{LINT_SPAN}"


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
