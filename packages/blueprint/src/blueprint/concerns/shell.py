"""Shell scripts run in strict mode: an unset variable or a failed pipe stops the script, not the next step.

A shell has no type checker; `set -u` and `pipefail` are the nearest thing, and `-e` stops at the first failure.
Only executable scripts are judged: a non-executable .sh is a library its caller sets the modes for.
Research: openspec/changes/blueprint-skill/research/shell-and-secrets.md.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from blueprint.model import MOVE, Sub, check_each, failing, is_skipped, not_checked, override_toml, passing

if TYPE_CHECKING:
    from blueprint.model import Context, Finding

_STACKS = ("shell",)
_SET = re.compile(r"^\s*set\s+(.+)$", re.MULTILINE)
_LONG = {"errexit": "e", "nounset": "u", "pipefail": "pipefail"}
# The old marker of a script meant to collect failures (a probe, a report): still honoured, with a notice. Such a script
# is excused by an [[override]] id = "stack.shell.strict-mode" scoped to its path, in docs/blueprint/blueprint.toml.
_MARKER = re.compile(r"#\s*strict:\s*no -e\b[\s,:;-]*(.*)")
_ID = "stack.shell.strict-mode"
_SHEBANG = re.compile(r"^#!\s*(?:/usr/bin/env\s+)?\S*?(bash|sh|dash)\b")


def _modes(text: str) -> set[str]:
    """Every mode the script's `set` lines turn on: `e`, `u`, `pipefail`."""
    modes: set[str] = set()
    for args in _SET.findall(text):
        words = args.split("#", 1)[0].split()
        for at, word in enumerate(words):
            if not re.fullmatch(r"-[a-zA-Z]+", word):
                continue
            modes.update(word[1:].replace("o", ""))
            # `-o pipefail`, and `-euo pipefail`: an `o` among the flags takes the next word as an option name.
            if "o" in word and at + 1 < len(words):
                modes.add(_LONG.get(words[at + 1], words[at + 1]))
    return modes


def _missing(text: str) -> list[str]:
    shell = _SHEBANG.match(text)
    if shell is None:
        return []
    modes = _modes(text)
    want = ["e", "u"] if shell.group(1) != "bash" else ["e", "u", "pipefail"]
    return [f"-{m}" if len(m) == 1 else m for m in want if m not in modes]


def _strict_mode(ctx: Context) -> Finding:
    staged = ctx.git("ls-files", "-s", "-z")
    if staged is None:
        return not_checked("not a git repository")
    scripts = [
        entry.split("\t", 1)[1]
        for entry in staged.split("\0")
        if entry.startswith("100755 ") and "\t" in entry and not is_skipped(entry.split("\t", 1)[1], (*ctx.profile.ignore, ".beads"))
    ]
    judged = 0
    loose: list[str] = []
    excused: list[str] = []
    for rel in scripts:
        text = ctx.read(rel) or ""
        if _SHEBANG.match(text) is None:
            continue
        judged += 1
        if not (missing := _missing(text)):
            continue
        if (override := ctx.excused(_ID, rel)) is not None:
            excused.append(f"{rel} by override ({override.reason})")
            continue
        if (marker := _MARKER.search(text)) and "-e" in missing:
            reason = marker.group(1).strip() or "<why this script runs on after a failure>"
            toml = override_toml(_ID, rel, reason, expires=ctx.expiry_hint())
            ctx.notices.append(
                f"{rel} carries `# strict: no -e`, still honoured but the old shape: {MOVE}, then delete the comment:\n{toml}"
            )
            missing = [m for m in missing if m != "-e"]
            excused.append(f"{rel} by an old `# strict: no -e` comment (see the notice)")
        if missing:
            loose.append(f"{rel} (no {', '.join(missing)})")
    if loose:
        shown = ", ".join(loose[:6]) + (f", and {len(loose) - 6} more" if len(loose) > 6 else "")
        return failing(
            f"{len(loose)} of {judged} scripts not in strict mode: {shown}",
            "`set -euo pipefail` after the header (a /bin/sh script: `set -eu`); a script that must run on after a failure "
            f'is excused by an [[override]] id = "{_ID}" with scope = "<script path>" in docs/blueprint/blueprint.toml',
        )
    note = f", {len(excused)} excused: {'; '.join(excused)}" if excused else ""
    return passing(f"{judged} executable scripts, each in strict mode{note}")


@check_each("stack.shell-strict", "executable shell scripts run in strict mode (-e, -u, pipefail)", layer="stack")
def shell_strict(ctx: Context) -> list[Sub]:
    """One row under whichever shell stack the repo has."""
    statement = "every executable script sets -e, -u and (bash) pipefail, or says why it drops -e"
    return [Sub(f"stack/{s}", f"stack.{s}.strict-mode", statement, _strict_mode(ctx)) for s in _STACKS if s in ctx.profile.stacks]
