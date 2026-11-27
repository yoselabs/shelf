"""The secret scanner: gitleaks is pinned (mise) and run from the hooks or the gate (git-hooks), over the changed code only.

Its own plugin (`secret-scan`) because it reads two others' files: it requires mise and git-hooks, so switching either off switches it off
(mission blueprint-plugins, step 4). The sops rows stay with `secrets`.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from blueprint.model import check, failing, passing

if TYPE_CHECKING:
    from blueprint.model import Context, Finding

_SCANNER_PIN = re.compile(r"^\s*[\"']?[\w:/.@-]*gitleaks[\w/.@-]*[\"']?\s*=", re.MULTILINE)
_SCANNER_RUN = re.compile(r"blueprint\.secret_scan|blueprint gate hook|\bgitleaks\b")
_FULL_SCAN = re.compile(r"secret_scan\s+full\b|gitleaks\s+git(?!\s+--(?:staged|pre-commit|log-opts))")


@check("secrets.scanner", "gitleaks is pinned in mise.toml and the hooks or the gate run it over the changed code, not the whole history")
def scanner(ctx: Context) -> Finding:
    """Sops seals what is meant to be secret; the scanner catches what was never meant to be committed (a key in code, a `.env`)."""
    if ctx.git("rev-parse", "--git-dir") is None:
        return ctx.not_a_repository()
    if not _SCANNER_PIN.search(ctx.read("mise.toml") or ""):
        return failing(
            "no gitleaks pin in mise.toml (ADR 0024: every tool the repo runs is pinned)",
            'add `gitleaks = "<version>"` under [tools] in mise.toml, then `mise lock`',
        )
    wired = {name: text for name in ("justfile", ".pre-commit-config.yaml") if _SCANNER_RUN.search(text := ctx.read(name) or "")}
    if not wired:
        return failing(
            "gitleaks is pinned but neither the justfile nor .pre-commit-config.yaml runs it",
            "add the pre-commit hook `uv run blueprint gate hook` (it runs the staged scan), and `... range` to the gate",
        )
    # Only the hook config: a justfile may keep a `full` recipe for the release gate (`check-all`).
    slow = [name for name, text in wired.items() if name == ".pre-commit-config.yaml" and _FULL_SCAN.search(text)]
    if slow:
        return failing(
            f"the whole history is scanned on every run ({', '.join(slow)}): the `full` mode is for a release tag",
            "run the staged scan in the commit hook and `range` in the gate",
        )
    return passing(f"gitleaks pinned; run from {', '.join(sorted(wired))}")
