"""A generated file is current: the generator writes into a temp folder, and what it wrote must equal the committed files.

Declared in the repo's pyproject.toml, one entry per generator (blueprint renders a `generated-<name>` step for each):

    [[tool.blueprint.gate.generated]]
    name = "contract"
    command = "uv run python scripts/contract.py --out {out}"   # {out}: a folder to write the outputs into, at their repo paths
    outputs = ["contract"]                                      # files or folders, relative to the repo
    reads = ["src/*", "scripts/*"]                              # optional: what the generator reads (fnmatch); absent: any change
    needs = ["ui-install"]                                      # optional: recipes run first (just dependencies; a private recipe works)

The command runs in the repo root. A folder output is compared whole: a file the generator did not write is "not generated" (a leftover),
a file it wrote and the repo lacks is "missing". The repo is never written; the fix is the same command with `{out}` as `.`.

Usage: python -m blueprint.generated [--repo DIR] NAME
Exit 0 current · 1 differs · 2 could not run (unknown name, generator failed).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

from blueprint.gate_py import manifest

_TIMEOUT = 3600.0  # seconds a generator may take


def entries(repo: Path) -> dict[str, dict[str, object]]:  # object: parsed TOML values
    """The declared generators by name."""
    data = tomllib.loads(manifest(repo).read_text(encoding="utf-8"))
    declared = data.get("tool", {}).get("blueprint", {}).get("gate", {}).get("generated", [])
    return {str(e["name"]): e for e in declared if isinstance(e, dict) and "name" in e}


def _output_files(root: Path, output: str) -> list[str]:
    """The files of one output under `root`, as paths relative to it (the output itself when it is a file)."""
    path = root / output
    if path.is_file():
        return [output]
    if path.is_dir():
        return sorted(p.relative_to(root).as_posix() for p in path.rglob("*") if p.is_file())
    return []


def differences(repo: Path, built: Path, outputs: list[str]) -> list[str]:
    """One line per file that differs between the repo and what the generator built."""
    found: list[str] = []
    for output in outputs:
        want, have = set(_output_files(built, output)), set(_output_files(repo, output))
        found += [f"{rel}: missing (the generator writes it)" for rel in sorted(want - have)]
        found += [f"{rel}: not generated (a leftover)" for rel in sorted(have - want)]
        found += [
            f"{rel}: differs from what the generator writes"
            for rel in sorted(want & have)
            if (built / rel).read_bytes() != (repo / rel).read_bytes()
        ]
    return found


def check(repo: Path, name: str) -> int:
    """Run the named generator into a temp folder and compare; the exit code."""
    declared = entries(repo)
    if name not in declared:
        sys.stderr.write(f"generated: no [[tool.blueprint.gate.generated]] named {name!r} (declared: {', '.join(declared) or 'none'})\n")
        return 2
    entry = declared[name]
    command, outputs = str(entry["command"]), [str(o) for o in entry.get("outputs", [])]  # type: ignore[attr-defined]
    with tempfile.TemporaryDirectory(prefix="generated-") as tmp:
        built = Path(tmp)
        done = subprocess.run(command.replace("{out}", str(built)), shell=True, cwd=repo, check=False, timeout=_TIMEOUT)  # noqa: S602 -- the repo's own declared command
        if done.returncode != 0:
            sys.stderr.write(f"generated {name}: the generator exited {done.returncode}: {command}\n")
            return 2
        found = differences(repo, built, outputs)
    if not found:
        sys.stdout.write(f"generated {name}: {', '.join(outputs)} current\n")
        return 0
    sys.stderr.write(f"generated {name}: {len(found)} file(s) differ from what the generator writes:\n")
    sys.stderr.write("".join(f"  {line}\n" for line in found))
    sys.stderr.write(f"regenerate and commit: {command.replace('{out}', '.')}\n")
    return 1


def main(argv: list[str]) -> int:
    """The command line."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=".", type=Path, help="the repository (default: cwd)")
    parser.add_argument("name", help="the generator's name in [[tool.blueprint.gate.generated]]")
    args = parser.parse_args(argv)
    return check(args.repo.resolve(), args.name)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
