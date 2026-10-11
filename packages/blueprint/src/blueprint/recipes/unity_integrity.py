#!/usr/bin/env python3
"""Unity project hygiene: every asset has a .meta, every .meta an asset, GUIDs unique, Force Text, Visible Meta Files.

A blueprint recipe (`blueprint recipe unity-integrity > tools/unity_integrity.py`): the repo copies it and owns the copy.
Stdlib only, so the gate and a prek hook run it without an environment.

Usage: unity_integrity.py [project_root]; prints one line per finding and exits 1 on any.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_GUID = re.compile(r"^guid: ([0-9a-f]{32})\s*$", re.MULTILINE)
_SETTINGS = (
    ("EditorSettings.asset", r"^\s*m_SerializationMode: (\d+)", "2", "Asset Serialization must be Force Text"),
    ("VersionControlSettings.asset", r"^\s*m_Mode: (.+)$", "Visible Meta Files", "Version Control mode must be Visible Meta Files"),
)


def _importable(path: Path, root: Path) -> bool:
    # Unity skips dot-prefixed names, names ending in ~, and *.tmp, in any folder of the path.
    parts = path.relative_to(root).parts
    return not any(p.startswith(".") or p.endswith("~") for p in parts) and path.suffix != ".tmp"


def _asset_folders(root: Path) -> list[Path]:
    # Only embedded packages (a folder of Packages/ with a package.json) carry their own metas.
    folders = [root / "Assets"] if (root / "Assets").is_dir() else []
    return folders + [p.parent for p in sorted((root / "Packages").glob("*/package.json"))]


def _meta_problems(root: Path) -> list[str]:
    problems: list[str] = []
    guids: dict[str, Path] = {}
    for folder in _asset_folders(root):
        for path in sorted(folder.rglob("*")):
            if not _importable(path, root):
                continue
            rel = path.relative_to(root).as_posix()
            if path.suffix != ".meta":
                if not Path(f"{path}.meta").exists():
                    problems.append(f"asset without .meta: {rel}")
                continue
            if not path.with_suffix("").exists():
                problems.append(f"orphan meta (no asset): {rel}")
            found = _GUID.search(path.read_text(errors="replace"))
            if found is None:
                problems.append(f"meta without a 32-hex guid: {rel}")
            elif found[1] in guids:
                problems.append(f"duplicate guid {found[1]}: {rel} and {guids[found[1]].relative_to(root).as_posix()}")
            else:
                guids[found[1]] = path
    return problems


def _setting_problems(root: Path) -> list[str]:
    problems: list[str] = []
    for file, pattern, want, why in _SETTINGS:
        path = root / "ProjectSettings" / file
        found = re.search(pattern, path.read_text(errors="replace") if path.is_file() else "", re.MULTILINE)
        value = found[1].strip() if found else ""
        if value != want:
            problems.append(f"ProjectSettings/{file}: {why} (found {value or 'nothing'!r}, want {want!r})")
    return problems


def main(argv: list[str]) -> int:
    """Check the Unity project at argv[0] (default: cwd)."""
    root = Path(argv[0] if argv else ".").resolve()
    problems = _meta_problems(root) + _setting_problems(root)
    for line in problems:
        sys.stdout.write(line + "\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
