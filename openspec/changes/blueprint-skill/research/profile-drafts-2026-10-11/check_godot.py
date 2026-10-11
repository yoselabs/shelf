"""Static integrity of a Godot 4 project, no editor needed: the checks the headless import log does not make.

Why: `godot --headless --import` only parses what the editor loads (main scene, project theme); a broken ext_resource
or a garbage line in any other scene or .tres passes it silently (seen on Godot 4.7.2, lifesim scratch copy, 2026-10-11).

Usage: python3 tools/check_godot.py <folder holding project.godot> [csproj]
Fails (exit 1) on:
  - a .tscn/.tres whose header is not `[gd_scene|gd_resource ... format=3 ...]`
  - a line at top level that is not a [section], a `key = value`, a comment or blank (garbage)
  - an ext_resource whose path does not exist, or whose uid differs from the target's uid
  - ExtResource("id") / SubResource("id") with no declaring section; an ext_resource never used
  - a .cs/.gd/.gdshader without its committed .uid sibling
  - Godot.NET.Sdk/x.y.z in the csproj disagreeing with config/features in project.godot (major.minor)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HEADER = re.compile(r"^\[(gd_scene|gd_resource)\b.*\bformat=3\b.*\]$")
SECTION = re.compile(r"^\[(\w+)([^\]]*)\]$")
KEYVAL = re.compile(r'^("[^"]*"|[\w/.:\-]+)\s*=')
ATTR = re.compile(r'(\w+)=("([^"]*)"|[^\s\]]+)')
USE = re.compile(r'\b(ExtResource|SubResource)\(\s*"?([\w\-]+)"?\s*\)')
UID = re.compile(r'uid="(uid://[^"]+)"')
SCRIPT_EXT = {".cs", ".gd", ".gdshader"}
SKIP = {".godot", "bin", "obj", ".git"}


def depth_delta(line: str) -> int:
    """Net open brackets in a line, ignoring quoted strings."""
    delta, quoted, i = 0, False, 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and quoted:
            i += 1
        elif ch == '"':
            quoted = not quoted
        elif not quoted and ch in "[{(":
            delta += 1
        elif not quoted and ch in "]})":
            delta -= 1
        i += 1
    return delta


def uid_of(root: Path, target: Path) -> str | None:
    """The uid a resource file declares: its own header, its .uid sibling, or its .import file."""
    sibling = Path(f"{target}.uid")
    if sibling.is_file():
        return sibling.read_text().strip() or None
    imported = Path(f"{target}.import")
    if imported.is_file() and (m := re.search(r'^uid="(uid://[^"]+)"', imported.read_text(), re.M)):
        return m.group(1)
    if target.suffix in {".tscn", ".tres"} and target.is_file():
        first = target.read_text(errors="replace").splitlines()[:1]
        m = UID.search(first[0]) if first else None
        return m.group(1) if m else None
    return None


def check_file(root: Path, path: Path) -> list[str]:
    rel, errors = path.relative_to(root).as_posix(), []
    lines = path.read_text(errors="replace").splitlines()
    if not lines or not HEADER.match(lines[0].strip()):
        return [f"{rel}:1 header is not [gd_scene|gd_resource ... format=3]"]
    declared: dict[str, str] = {}
    used: set[str] = set()
    ext_ids: dict[str, int] = {}
    depth = 0
    for n, raw in enumerate(lines, 1):
        line = raw.strip()
        if depth == 0 and line and not line.startswith(";"):
            sec = SECTION.match(line)
            if sec:
                attrs = {k: (q or v).strip('"') for k, v, q in ATTR.findall(sec.group(2))}
                if sec.group(1) == "ext_resource" and n > 1:
                    target = root / attrs.get("path", "").removeprefix("res://")
                    ext_ids[attrs.get("id", "")] = n
                    declared[attrs.get("id", "")] = "ext"
                    if not attrs.get("path", "").startswith("res://") or not target.exists():
                        errors.append(f"{rel}:{n} ext_resource path {attrs.get('path')!r} does not exist")
                    elif attrs.get("uid") and (want := uid_of(root, target)) and want != attrs["uid"]:
                        errors.append(f"{rel}:{n} ext_resource uid {attrs['uid']} != {want} in {attrs['path']}")
                elif sec.group(1) == "sub_resource":
                    declared[attrs.get("id", "")] = "sub"
            elif not KEYVAL.match(line) and n > 1:
                errors.append(f"{rel}:{n} not a section, key = value, or comment: {line[:60]!r}")
        used.update(f"{kind}:{ident}" for kind, ident in USE.findall(line) if not line.startswith("[ext_resource"))
        depth = max(0, depth + depth_delta(line if depth else line if not SECTION.match(line) else ""))
    for use in sorted(used):
        kind, ident = use.split(":")
        if declared.get(ident) != ("ext" if kind == "ExtResource" else "sub"):
            errors.append(f"{rel} {kind}({ident!r}) has no declaring section")
    errors += [f"{rel}:{n} ext_resource id {i!r} is never used" for i, n in ext_ids.items() if f"ExtResource:{i}" not in used]
    return errors


def check_uids(root: Path) -> list[str]:
    scripts = (p for p in root.rglob("*") if p.suffix in SCRIPT_EXT and not SKIP & set(p.relative_to(root).parts))
    return [f"{p.relative_to(root).as_posix()} has no committed .uid file" for p in scripts if not Path(f"{p}.uid").is_file()]


def check_version(root: Path, csproj: Path | None) -> list[str]:
    project = (root / "project.godot").read_text()
    feat = re.search(r'config/features=PackedStringArray\("(\d+\.\d+)"', project)
    sdk = re.search(r"Godot\.NET\.Sdk/(\d+\.\d+)\.\d+", csproj.read_text()) if csproj else None
    if feat and sdk and feat.group(1) != sdk.group(1):
        return [f"project.godot says Godot {feat.group(1)}, {csproj.name} says Godot.NET.Sdk {sdk.group(1)}"]
    return []


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    csproj = Path(sys.argv[2]) if len(sys.argv) > 2 else next(iter(sorted(root.glob("*.csproj"))), None)
    files = (p for p in sorted(root.rglob("*")) if p.suffix in {".tscn", ".tres"} and not SKIP & set(p.relative_to(root).parts))
    errors = [e for f in files for e in check_file(root, f)] + check_uids(root) + check_version(root, csproj)
    print("\n".join(errors) or "godot surface: clean")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
