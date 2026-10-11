#!/usr/bin/env python3
"""Unity project hygiene gate: .meta pairing, unique GUIDs, Force Text, Visible Meta Files. Stdlib only.

Usage: unity_integrity.py [project_root]   exit 1 on any finding.
"""
import re
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
problems: list[str] = []


def importable(p: Path) -> bool:
    # Unity ignores dot-prefixed names, names ending in ~, and *.tmp, in any folder of the path.
    return not any(part.startswith(".") or part.endswith("~") for part in p.relative_to(root).parts) and p.suffix != ".tmp"


guids: dict[str, Path] = {}
for top in ("Assets", "Packages"):
    base = root / top
    if not base.is_dir():
        continue
    if top == "Packages":  # only embedded packages (a folder with package.json) carry their own metas
        bases = [d.parent for d in base.glob("*/package.json")]
    else:
        bases = [base]
    for b in bases:
        for p in sorted(b.rglob("*")):
            if not importable(p) or p == b:
                continue
            if p.suffix == ".meta":
                target = p.with_suffix("")
                if not target.exists():
                    problems.append(f"orphan meta (no asset): {p.relative_to(root)}")
                m = re.search(r"^guid: ([0-9a-f]{32})\s*$", p.read_text(errors="replace"), re.M)
                if not m:
                    problems.append(f"meta without a 32-hex guid: {p.relative_to(root)}")
                elif m[1] in guids:
                    problems.append(f"duplicate guid {m[1]}: {p.relative_to(root)} and {guids[m[1]].relative_to(root)}")
                else:
                    guids[m[1]] = p
            elif not Path(str(p) + ".meta").exists():
                problems.append(f"asset without .meta: {p.relative_to(root)}")


def setting(file: str, pattern: str, want: str, why: str) -> None:
    f = root / "ProjectSettings" / file
    text = f.read_text(errors="replace") if f.is_file() else ""
    m = re.search(pattern, text, re.M)
    if not m or m[1].strip() != want:
        problems.append(f"ProjectSettings/{file}: {why} (found {m[1].strip() if m else 'nothing'!r}, want {want!r})")


setting("EditorSettings.asset", r"^\s*m_SerializationMode: (\d+)", "2", "Asset Serialization must be Force Text")
setting("VersionControlSettings.asset", r"^\s*m_Mode: (.+)$", "Visible Meta Files", "Version Control mode must be Visible Meta Files")

for line in problems:
    print(line)
sys.exit(1 if problems else 0)
