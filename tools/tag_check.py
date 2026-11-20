#!/usr/bin/env python3
"""Every package version on the released branch has its tag: `<name>-v<version>` on origin.

A version bump merged to main with no tag is an unreleased package that reads as released (anyllm 0.8.0 sat so, 2026-11-09). The catalog
test only compares the `release` string with pyproject; this is the check that the tag exists. It runs before every push and reads
`origin/main` (fetched best effort), not the branch being pushed: a release is bump, merge, then tag, so a feature branch cannot be
tagged yet, but main with an untagged version blocks the next push until the tag is made or the package is explicitly allowed.

`tools/tag_check_allow.toml` lists packages allowed to stay untagged, each with its reason. An entry for a package that is tagged, gone, or
not a package fails too, so the list never outlives the need. Tags come from `git ls-remote --tags origin`; offline, local tags are used and
that is said. Stdlib only, so it runs as bare `python3 -I`.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

ALLOW_FILE = Path(__file__).with_name("tag_check_allow.toml")


def git(repo: Path, *args: str) -> str | None:
    """What git prints, or None when it fails."""
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    return done.stdout if done.returncode == 0 else None


def versions(repo: Path, rev: str) -> dict[str, str]:
    """{package: version} of every `packages/*/pyproject.toml` at `rev`."""
    listing = git(repo, "ls-tree", "--name-only", rev, "packages/") or ""
    out: dict[str, str] = {}
    for path in listing.splitlines():
        name = path.removeprefix("packages/")
        text = git(repo, "show", f"{rev}:{path}/pyproject.toml")
        version = tomllib.loads(text)["project"].get("version") if text else None
        if isinstance(version, str):
            out[name] = version
    return out


def remote_tags(repo: Path, remote: str) -> tuple[set[str], bool]:
    """(tags, from_remote). Falls back to the local tags when the remote cannot be asked."""
    remote_listing = git(repo, "ls-remote", "--tags", "--refs", remote)
    if remote_listing is not None:
        return {line.split("refs/tags/", 1)[1] for line in remote_listing.splitlines() if "refs/tags/" in line}, True
    return set((git(repo, "tag", "--list") or "").split()), False


def problems(found: dict[str, str], tags: set[str], allow: dict[str, str]) -> list[str]:
    """The lines to print: untagged packages not allowed, and allowance entries that no longer mean anything."""
    out = [
        f"{name} {version}: no tag {name}-v{version} (tag the commit that released it, or allow it in {ALLOW_FILE.name} with a reason)"
        for name, version in sorted(found.items())
        if f"{name}-v{version}" not in tags and name not in allow
    ]
    for name, reason in sorted(allow.items()):
        if name not in found:
            out.append(f"{ALLOW_FILE.name}: {name} is not a package on the checked branch; delete its entry")
        elif f"{name}-v{found[name]}" in tags:
            out.append(f"{ALLOW_FILE.name}: {name} {found[name]} is tagged; delete its entry ({reason})")
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--rev", default="origin/main", help="the branch whose versions must be tagged")
    parser.add_argument("--allow", type=Path, default=ALLOW_FILE)
    args = parser.parse_args(argv)
    repo = args.repo
    git(repo, "fetch", "--quiet", args.remote, args.rev.removeprefix(f"{args.remote}/"))  # best effort: a stale ref only checks older state
    if git(repo, "rev-parse", "--verify", "--quiet", args.rev) is None:
        sys.stderr.write(f"tag-check: {args.rev} not found; nothing to check\n")
        return 0
    tags, from_remote = remote_tags(repo, args.remote)
    if not from_remote:
        sys.stderr.write(f"tag-check: {args.remote} unreachable; checked the local tags\n")
    allow = tomllib.loads(args.allow.read_text(encoding="utf-8")).get("allow", {}) if args.allow.is_file() else {}
    bad = problems(versions(repo, args.rev), tags, allow)
    for line in bad:
        sys.stderr.write(f"tag-check: {line}\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
