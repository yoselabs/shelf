"""Every `image:` in a tracked compose file is pinned by digest: `name:tag@sha256:<64 hex>` (tag for the human, digest for the machine).

Run by the rendered `images` step when `[tool.blueprint.gate] image-pins = true`:
`python -m blueprint.compose_pins [--exempt PREFIX ...] [file ...]`. One process reads every file; no Docker, no network.
No files: every tracked `*compose*.yml` / `*compose*.yaml` (git ls-files).
`--exempt PREFIX` (config `image-pin-exempt`) excuses an image whose text starts with PREFIX, e.g. the repo's own image built from the
same commit (`ghcr.io/org/app:${IMAGE_TAG:?`), which has no digest to write.
A line scan, not a YAML parse: compose's `image:` is one scalar on one line, and the check needs no interpolation.
Exit 1 with one `path:line message` per unpinned image.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
IMAGE = re.compile(r"^\s*(?:-\s+)?image:\s*(?P<value>.*?)\s*$")
COMPOSE = re.compile(r"compose[^/]*\.ya?ml$")


def _value(raw: str) -> str:
    """The scalar without a trailing ` # comment` and its quotes."""
    raw = re.sub(r"\s+#.*$", "", raw) if not raw.startswith(("'", '"')) else raw
    return raw.strip().strip("'\"")


def check_text(text: str, rel: str, exempt: tuple[str, ...] = ()) -> list[str]:
    """One finding per `image:` of `text` that is neither digest-pinned nor exempt."""
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        match = IMAGE.match(line)
        image = _value(match["value"]) if match else ""
        if image and not DIGEST.search(image) and not any(image.startswith(prefix) for prefix in exempt):
            findings.append(f"{rel}:{number} {image!r} has no @sha256:<64 hex> digest")
    return findings


def tracked() -> list[Path]:
    """Tracked compose files (git ls-files)."""
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True, timeout=30).stdout.splitlines()
    return [Path(f) for f in out if COMPOSE.search(f)]


def main(argv: list[str]) -> int:
    """Check the given compose files, or every tracked one."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--exempt", action="append", default=[], metavar="PREFIX", help="an image prefix to excuse; repeatable")
    parser.add_argument("files", nargs="*", type=Path, help="compose files to check; default: every tracked one")
    args = parser.parse_args(argv)
    files: list[Path] = args.files or tracked()
    exempt = tuple(args.exempt)
    errors = [
        e
        for f in files
        for e in check_text(f.read_text(encoding="utf-8", errors="replace"), f.as_posix(), exempt)  # lossy-ok: parse: a yes/no per line
    ]
    sys.stdout.write(("\n".join(errors) or f"compose pins: {len(files)} file(s) clean") + "\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
