"""Shell scripts run in strict mode: an unset variable or a failed pipe stops the script, not the next step.

A shell has no type checker; `set -u` and `pipefail` are the nearest thing, and `-e` stops at the first failure.
Only executable scripts are judged: a non-executable .sh is a library its caller sets the modes for.
Research: openspec/changes/blueprint-skill/research/shell-and-secrets.md.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from blueprint.model import Sub, check_each, failing, is_skipped, not_checked, passing

if TYPE_CHECKING:
    from blueprint.model import Context, Finding

# The full shell stack, and a few helper scripts beside another language: strict mode applies to both.
_STACKS = ("shell", "shell-scripts")
_SET = re.compile(r"^\s*set\s+(.+)$", re.MULTILINE)
_LONG = {"errexit": "e", "nounset": "u", "pipefail": "pipefail"}
# A script meant to collect failures (a probe, a report) runs on; it says so, with why.
_WAIVER = re.compile(r"#\s*strict:\s*no -e\b")
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
    want = ["u"] if shell.group(1) != "bash" else ["u", "pipefail"]
    if not _WAIVER.search(text):
        want.insert(0, "e")
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
    for rel in scripts:
        text = ctx.read(rel) or ""
        if _SHEBANG.match(text) is None:
            continue
        judged += 1
        if missing := _missing(text):
            loose.append(f"{rel} (no {', '.join(missing)})")
    if loose:
        shown = ", ".join(loose[:6]) + (f", and {len(loose) - 6} more" if len(loose) > 6 else "")
        return failing(
            f"{len(loose)} of {judged} scripts not in strict mode: {shown}",
            "`set -euo pipefail` after the header (a /bin/sh script: `set -eu`); a script that must run on after a failure "
            "keeps -u and pipefail and says `# strict: no -e, <reason>`",
        )
    return passing(f"{judged} executable scripts, each in strict mode")


@check_each("stack.shell-strict", "executable shell scripts run in strict mode (-e, -u, pipefail)", layer="stack")
def shell_strict(ctx: Context) -> list[Sub]:
    """One row under whichever shell stack the repo has."""
    statement = "every executable script sets -e, -u and (bash) pipefail, or says why it drops -e"
    return [Sub(f"stack/{s}", f"stack.{s}.strict-mode", statement, _strict_mode(ctx)) for s in _STACKS if s in ctx.profile.stacks]
