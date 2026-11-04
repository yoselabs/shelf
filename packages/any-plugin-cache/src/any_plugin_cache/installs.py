"""What Claude Code has installed: <claude dir>/plugins/cache/<marketplace>/<plugin>/<version>/, and the version it records as active."""

from __future__ import annotations

import json
from pathlib import Path


def version_key(name: str) -> tuple[int, ...] | None:
    """A dotted version as an orderable tuple of ints ("0.23.56" > "0.9.1"); None when `name` is not a plain dotted-int version."""
    parts = name.split(".")
    if not name or not all(p.isascii() and p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


def installs(claude_dir: Path, plugin: str, marker: str) -> dict[str, Path]:
    """{version: dir} of the cache dirs of `plugin` (any marketplace) that hold the file `marker` (a path relative to the dir).
    Half-copied dirs and non-version names are left out; the same version in two marketplaces keeps the first by name."""
    out: dict[str, Path] = {}
    for d in sorted((claude_dir / "plugins" / "cache").glob(f"*/{plugin}/*")):
        if version_key(d.name) and (d / marker).is_file():
            out.setdefault(d.name, d)
    return out


def installed_version(claude_dir: Path, plugin: str) -> str:
    """The version `installed_plugins.json` records for `plugin` at user scope, else "" (no file, unreadable, or no such entry)."""
    try:
        recs = json.loads((claude_dir / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))["plugins"]
    except (OSError, ValueError, KeyError, TypeError):
        return ""
    for name, entries in recs.items():
        if name.split("@")[0] == plugin and isinstance(entries, list):
            for e in entries:
                if isinstance(e, dict) and e.get("scope") == "user":
                    return Path(str(e.get("installPath") or "")).name
    return ""


def pin_ok(found: dict[str, Path], version: str) -> bool:
    """A pin must name an installed dir: True only when `version` is one of `found`."""
    return version in found


def previous(found: dict[str, Path], current: str) -> str:
    """The newest installed version strictly below `current` (the rollback target), "" when there is none."""
    cur = version_key(current) or ()
    below = [v for v in found if (version_key(v) or ()) < cur]
    return max(below, key=lambda v: version_key(v) or ()) if below else ""


def behind(found: dict[str, Path], version: str) -> int:
    """How many installed versions are newer than `version` (0 when it is the newest or not a version)."""
    mine = version_key(version)
    return sum(1 for v in found if mine and (version_key(v) or ()) > mine)
