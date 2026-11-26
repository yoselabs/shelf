#!/usr/bin/env python3
"""What a blueprint release changes for the repositories it judges: run `blueprint check` over the corpus with two versions, print the diff.

A new or changed checkpoint can fail dozens of repos at once; that was learned after the release, by hand (blueprint 0.14.x, 2026-11-23).
This runs before the tag: `--base` is a rev (default: the newest `blueprint-v*` tag), `--head` another rev or, by default, the working
tree. Both engines are the stdlib-only source of `packages/blueprint/src` at that rev, so nothing is installed. Only changes are printed:
a repo whose verdicts did not move costs one count in the footer. A repo missing on this machine, or one the engine cannot judge, is named
and skipped. `tools/corpus.toml` lists the repositories. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

CORPUS = Path(__file__).with_name("corpus.toml")
SRC = "packages/blueprint/src"
RUN_TIMEOUT = 300.0  # seconds one repo may take: a hung audit must not hang the release
JOBS = 4


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True, timeout=RUN_TIMEOUT).stdout


def newest_tag(repo: Path) -> str:
    tags = [t for t in git(repo, "tag", "--list", "blueprint-v*", "--sort=-version:refname").split() if t]
    if not tags:
        sys.exit("corpus-diff: no blueprint-v* tag; pass --base")
    return tags[0]


def export_src(repo: Path, rev: str, into: Path) -> Path:
    """`packages/blueprint/src` as of `rev` (a rev, or `WORKTREE` for the checked-out files) under `into`; the PYTHONPATH to use."""
    if rev == "WORKTREE":
        return repo / SRC
    archive = subprocess.run(["git", "archive", rev, SRC], cwd=repo, capture_output=True, check=True, timeout=RUN_TIMEOUT).stdout
    subprocess.run(["tar", "-x", "-C", str(into)], input=archive, check=True, timeout=RUN_TIMEOUT)
    return into / SRC


def start(src: Path, target: Path) -> subprocess.Popen[str]:
    """One engine judging one repo, started; read it with `finish`."""
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "PYTHONPATH": str(src), "HOME": str(Path.home())}
    argv = [sys.executable, "-m", "blueprint", "check", "--repo", str(target), "--json"]
    return subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env)


def finish(proc: subprocess.Popen[str]) -> dict[str, str] | None:
    """{row id: verdict}, or None when the engine could not judge the repo."""
    try:
        out, _ = proc.communicate(timeout=RUN_TIMEOUT)
        data = json.loads(out)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        proc.kill()
        proc.communicate()
        return None
    return {row["id"]: row["verdict"] for row in data.get("rows", [])}


def audit_all(jobs: list[tuple[Path, Path]]) -> list[dict[str, str] | None]:
    """Every (engine src, repo) judged, at most JOBS processes at once; results in the order of `jobs`."""
    results: list[dict[str, str] | None] = [None] * len(jobs)
    running: list[tuple[int, subprocess.Popen[str]]] = []
    queue = list(enumerate(jobs))
    while queue or running:
        while queue and len(running) < JOBS:
            index, (src, target) = queue.pop(0)
            running.append((index, start(src, target)))
        index, proc = running.pop(0)
        results[index] = finish(proc)
    return results


def moved(old: dict[str, str], new: dict[str, str]) -> list[str]:
    """One line per row whose verdict differs, or that exists in one engine only."""
    lines = []
    for row in sorted(old.keys() | new.keys()):
        before, after = old.get(row, "absent"), new.get(row, "absent")
        if before != after:
            lines.append(f"{row}: {before} -> {after}")
    return lines


def passing(rows: dict[str, str]) -> int:
    return sum(1 for verdict in rows.values() if verdict == "passing")


def report(results: dict[str, tuple[dict[str, str], dict[str, str]] | None], missing: list[str]) -> list[str]:
    out: list[str] = []
    still = 0
    for name, pair in sorted(results.items()):
        if pair is None:
            out.append(f"{name}: not judged (engine failed or timed out)")
            continue
        old, new = pair
        lines = moved(old, new)
        if not lines:
            still += 1
            continue
        out.append(f"{name}: {passing(old)} -> {passing(new)} passing of {len(new)}")
        out.extend(f"  {line}" for line in lines)
    out.append(f"unchanged: {still} of {len(results)} repos" + (f"; not on this machine: {', '.join(missing)}" if missing else ""))
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="the shelf checkout holding both engines")
    parser.add_argument("--base", help="rev of the engine to compare against (default: the newest blueprint-v* tag)")
    parser.add_argument("--head", default="WORKTREE", help="rev of the engine to judge (default: the checked-out files)")
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--root", type=Path, default=Path.home() / "Workspaces", help="where the corpus repositories are cloned")
    args = parser.parse_args(argv)
    names = tomllib.loads(args.corpus.read_text(encoding="utf-8"))["repos"]
    present = [n for n in names if (args.root / n).is_dir()]
    missing = [n for n in names if n not in present]
    base = args.base or newest_tag(args.repo)
    sys.stderr.write(f"corpus-diff: {base} -> {args.head} over {len(present)} repos\n")
    with tempfile.TemporaryDirectory() as tmp:
        old_dir, new_dir = Path(tmp) / "base", Path(tmp) / "head"
        old_dir.mkdir()
        new_dir.mkdir()
        old_src = export_src(args.repo, base, old_dir)
        new_src = export_src(args.repo, args.head, new_dir)
        jobs = [(src, args.root / name) for name in present for src in (old_src, new_src)]
        judged = audit_all(jobs)
    results: dict[str, tuple[dict[str, str], dict[str, str]] | None] = {}
    for index, name in enumerate(present):
        old, new = judged[2 * index], judged[2 * index + 1]
        results[name] = None if old is None or new is None else (old, new)
    sys.stdout.write("\n".join(report(results, missing)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
