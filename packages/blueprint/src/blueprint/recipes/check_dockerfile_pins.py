#!/usr/bin/env python3
"""Every image a Dockerfile pulls is pinned by digest: `name:tag@sha256:<64 hex>`.

Why: hadolint's DL3006/DL3007 force a tag, never a digest; a tag moves, a digest is the lockfile (seen 2026-10-11:
homelab's frigate image and a2kay's three Dockerfiles pull `python:3.12-slim`, `uv:0.13.0` by tag only).

A blueprint recipe (`blueprint recipe dockerfile-pins > tools/check_dockerfile_pins.py`): the repo copies it and owns the copy.
Stdlib only, no network. The digest is fetched elsewhere (`crane digest <image:tag>` or `docker buildx imagetools inspect`)
and bumped by an updater (Renovate `pinDigests`, or the repo's own report); this script only judges the files.

Usage: python3 -I tools/check_dockerfile_pins.py [--context NAME ...] [Dockerfile ...]
No files: every tracked Dockerfile, *.Dockerfile, Dockerfile.*, Containerfile (git ls-files; not *.dockerignore).
Checked: each `FROM [--platform=..] image [AS name]`, each `COPY --from=<image>` and `RUN --mount=...from=<image>`.
Exempt: `scratch`; a name that is an earlier stage alias or a stage number; a bare name in COPY --from / --mount from=
(no `:` `/` `@`) is a build context (`docker build --build-context shelf=..`), as is any --context NAME.
ARG defaults declared before the first FROM are substituted into the image; a variable with no default is a finding.
Exit 1 with one `path:line message` per image that lacks a digest.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
NAME = re.compile(r"(^|/)(Containerfile|Dockerfile(\.[^/]+)?|[^/]*\.Dockerfile)$")
VAR = re.compile(r"\$\{(\w+)(?::?-([^}]*))?\}|\$(\w+)")
ARG = re.compile(r"^ARG\s+(\w+)(?:=(\S*))?", re.IGNORECASE)
FROM = re.compile(r"^FROM\s+(?:--\S+\s+)*(\S+)(?:\s+AS\s+(\S+))?", re.IGNORECASE)
COPY_FROM = re.compile(r"^(?:COPY|ADD)\s+(?:--\S+\s+)*?--from=(\S+)", re.IGNORECASE)
MOUNT_FROM = re.compile(r"^RUN\s+.*?--mount=\S*?\bfrom=([^,\s]+)", re.IGNORECASE)


def logical_lines(text: str) -> list[tuple[int, str]]:
    """(first line number, instruction) with continuations joined and comment lines dropped."""
    out: list[tuple[int, str]] = []
    buf, start = "", 0
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if line.startswith("#") or (not line and not buf):
            continue
        start = start or n
        if line.endswith("\\"):
            buf += line[:-1].rstrip() + " "
            continue
        out.append((start, (buf + line).strip()))
        buf, start = "", 0
    if buf:
        out.append((start, buf.strip()))
    return out


def substitute(image: str, args: dict[str, str]) -> tuple[str, list[str]]:
    """The image with ARG defaults filled in, and the variables that stayed unresolved."""
    missing: list[str] = []

    def fill(m: re.Match[str]) -> str:
        name = m.group(1) or m.group(3)
        if name in args:
            return args[name]
        if m.group(2) is not None:
            return m.group(2)
        missing.append(name)
        return m.group(0)

    return VAR.sub(fill, image), missing


def judge(image: str, where: str, names: tuple[dict[str, str], set[str], set[str]], *, bare_is_context: bool) -> str | None:
    """A finding for one image reference at `where` (`path:line`), or None when it is exempt or pinned.

    `names` holds what the file has declared so far: ARG defaults, stage aliases, and the build contexts named on the command line.
    """
    args, stages, contexts = names
    resolved, missing = substitute(image, args)
    key = resolved.lower()
    if key == "scratch" or key in stages or key in contexts or key.isdigit():
        return None
    if missing:
        return f"{where} {image!r} uses ${missing[0]} with no ARG default before the first FROM: cannot tell what is pulled"
    if bare_is_context and not re.search(r"[:/@]", resolved):
        return None
    if not DIGEST.search(resolved):
        return f"{where} {resolved!r} has no @sha256:<64 hex> digest"
    return None


def check_file(path: Path, rel: str, contexts: set[str]) -> list[str]:
    """Every unpinned image in one Dockerfile."""
    args: dict[str, str] = {}
    stages: set[str] = set()
    seen_from = False
    errors: list[str] = []
    for n, text in logical_lines(path.read_text(errors="replace")):
        if m := FROM.match(text):
            seen_from = True
            err = judge(m.group(1), f"{rel}:{n}", (args, stages, contexts), bare_is_context=False)
            errors += [err] if err else []
            if m.group(2):
                stages.add(m.group(2).lower())
        elif not seen_from and (m := ARG.match(text)):
            if m.group(2) is not None:
                args[m.group(1)] = m.group(2).strip("\"'")
        elif m := (COPY_FROM.match(text) or MOUNT_FROM.match(text)):
            err = judge(m.group(1), f"{rel}:{n}", (args, stages, contexts), bare_is_context=True)
            errors += [err] if err else []
    return errors


def tracked() -> list[Path]:
    """Tracked Dockerfiles (git ls-files), else every one under the current folder."""
    try:
        files = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        files = [p.as_posix() for p in Path().rglob("*") if p.is_file() and ".git" not in p.parts]
    return [Path(f) for f in files if NAME.search(f) and not f.endswith(".dockerignore")]


def main(argv: list[str]) -> int:
    """Check the given Dockerfiles, or every tracked one."""
    contexts: set[str] = set()
    files: list[Path] = []
    it = iter(argv)
    for a in it:
        if a == "--context":
            contexts.add(next(it, "").lower())
        else:
            files.append(Path(a))
    files = files or tracked()
    errors = [e for f in files for e in check_file(f, f.as_posix(), contexts)]
    sys.stdout.write(("\n".join(errors) or f"dockerfile pins: {len(files)} file(s) clean") + "\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
