#!/usr/bin/env python3
"""The gate's state on a shared box: one test run at a time, and the trees that already passed.

Two jobs, both stdlib only so the script runs as bare `python3 -I`:

`lock -- CMD...` runs CMD under a box-wide lock, so gates started at once queue instead of thrashing (each test run
takes every core; four at once on one box took 11-14 min each instead of 2). A run that has to wait says so once,
naming the holder, and again when it gets the lock. The lock is an flock on `$GATE_LOCK_FILE`, default
`${XDG_CACHE_HOME:-~/.cache}/gate-test.lock`, held by CMD itself (the script execs it) and freed when CMD exits or
dies. A CMD run under the lock that asks for it again does not wait on itself (`GATE_LOCK_HELD`). It is off when
`CI` is set (a CI runner is single-tenant) or `GATE_LOCK=off`. Notices go to the file descriptor in
`$GATE_NOTICE_FD` when that is open (the gate's parallel runner points it at its terminal; a step's own output is
logged), else to stderr. Only the expensive step takes it, so the gate's other steps never wait on it.

`start`, `passed --gate NAME` and `pre-push --gate NAME -- CMD...` keep a record of the trees a gate passed, so a
push does not run the gate again on the exact content that just passed it:
- `start` (the gate's first step) notes the working tree's key: the tree `git add -A` would commit (tracked and
  untracked files, ignored ones left out) and the upstream merge-base (the base the changed-file steps diff against).
- `passed` (run only after every step passed) records the key when it is the same as at `start`, so a file edited
  during the run records nothing. The record is `gate-green` in the git common dir, shared by every worktree.
- `pre-push` skips CMD only when the working tree is clean, the pushed commit is HEAD (`PRE_COMMIT_TO_REF`, when the
  hook runner gives it) and HEAD's key is recorded for the gate; anything else, or any doubt, runs CMD.
A rebase onto a new upstream changes the tree, so the gate runs again.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

RECORD = "gate-green"
START = "gate-green.start"
_KEEP = 50  # trees remembered per repo
_OFF = frozenset({"0", "off", "false", "no"})


def _notice(text: str) -> None:
    line = f"{text}\n".encode()
    fd = os.environ.get("GATE_NOTICE_FD", "")
    if fd.isdigit():
        try:
            os.write(int(fd), line)
        except OSError:
            pass
        else:
            return
    sys.stderr.buffer.write(line)
    sys.stderr.flush()


def _exec(cmd: Sequence[str], env: dict[str, str]) -> int:
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        os.execvpe(cmd[0], list(cmd), env)  # noqa: S606 -- running the gate's own step is this tool's job
    except OSError as err:
        _notice(f"gate-state: cannot run {cmd[0]}: {err}")
        return 127


# ── the box-wide lock ───────────────────────────────────────────────────────────


def lock_file() -> Path:
    """Where the lock lives: `$GATE_LOCK_FILE`, else `gate-test.lock` in the user's cache dir."""
    named = os.environ.get("GATE_LOCK_FILE", "")
    if named:
        return Path(named)
    cache = os.environ.get("XDG_CACHE_HOME", "") or str(Path.home() / ".cache")
    return Path(cache) / "gate-test.lock"


def _lock_off() -> str | None:
    if os.environ.get("GATE_LOCK", "").strip().lower() in _OFF:
        return "GATE_LOCK=off"
    if os.environ.get("CI", "").strip().lower() not in {"", *_OFF}:
        return "CI"
    return None


def run_locked(cmd: Sequence[str]) -> int:
    """Exec `cmd` holding the box-wide lock (see the module docstring); returns only when it cannot exec."""
    env = dict(os.environ)
    path = lock_file()
    off = _lock_off()
    if off is not None:
        _notice(f"gate-lock: off ({off})")
        return _exec(cmd, env)
    if env.get("GATE_LOCK_HELD") == str(path):
        return _exec(cmd, env)
    try:
        import fcntl  # noqa: PLC0415 -- POSIX only; Windows runs without the lock
    except ImportError:
        _notice("gate-lock: off (no flock on this platform)")
        return _exec(cmd, env)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o666)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        holder = os.pread(fd, 512, 0).decode(errors="replace").strip() or "an unnamed run"
        _notice(f"gate-lock: waiting for {path}, held by {holder}")
        began = time.monotonic()
        fcntl.flock(fd, fcntl.LOCK_EX)
        _notice(f"gate-lock: acquired after {time.monotonic() - began:.0f}s")
    os.ftruncate(fd, 0)
    os.pwrite(fd, f"pid {os.getpid()} in {Path.cwd()} since {datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}\n".encode(), 0)
    os.set_inheritable(fd, True)  # noqa: FBT003 -- positional-only; the lock lives as long as the command holding it
    env["GATE_LOCK_HELD"] = str(path)
    return _exec(cmd, env)


# ── the record of trees that passed ─────────────────────────────────────────────


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str | None:
    """What git prints, stripped; None when git fails (not a repo, no upstream, ...)."""
    try:
        done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False, env=env)
    except OSError:
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def _git_path(repo: Path, name: str, *, common: bool) -> Path | None:
    if common:
        found = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
        return Path(found) / name if found else None
    found = _git(repo, "rev-parse", "--path-format=absolute", "--git-path", name)
    return Path(found) if found else None


def _base(repo: Path) -> str:
    return _git(repo, "merge-base", "HEAD", "@{upstream}") or "none"


def working_key(repo: Path) -> str | None:
    """`<tree> <base>` for the working tree as `git add -A` would commit it; None when git cannot say."""
    index = _git_path(repo, "index", common=False)
    if index is None:
        return None
    with tempfile.TemporaryDirectory() as scratch:
        temp_index = Path(scratch) / "index"
        if index.is_file():
            shutil.copyfile(index, temp_index)  # its stat cache keeps `add -A` from rehashing every file
        env = {**os.environ, "GIT_INDEX_FILE": str(temp_index)}
        if _git(repo, "add", "-A", env=env) is None:
            return None
        tree = _git(repo, "write-tree", env=env)
    return f"{tree} {_base(repo)}" if tree else None


def head_key(repo: Path) -> str | None:
    """`<tree> <base>` for HEAD; None when the working tree is not clean or git cannot say."""
    if _git(repo, "status", "--porcelain") != "":
        return None
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    return f"{tree} {_base(repo)}" if tree else None


def start(repo: Path) -> int:
    """Note the working tree's key as the gate starts; a repo git cannot read notes nothing."""
    path = _git_path(repo, START, common=False)
    key = working_key(repo)
    if path is None or key is None:
        return 0
    try:
        path.write_text(key + "\n")
    except OSError:
        path.unlink(missing_ok=True)
    return 0


def passed(repo: Path, gate: str) -> int:
    """Record the working tree as green for `gate` when it is the tree `start` noted. Never fails the gate."""
    begun = _git_path(repo, START, common=False)
    record = _git_path(repo, RECORD, common=True)
    if begun is None or record is None or not begun.is_file():
        _notice("gate-state: no start noted, nothing recorded")
        return 0
    noted = begun.read_text().strip()
    begun.unlink(missing_ok=True)
    key = working_key(repo)
    if key is None or key != noted:
        _notice("gate-state: the tree changed during the run, nothing recorded")
        return 0
    lines = [ln for ln in _read(record) if ln.split(" ")[:3] != [gate, *key.split(" ")]]
    lines.append(f"{gate} {key} {datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}")
    try:
        temp = record.with_name(f"{RECORD}.{os.getpid()}")
        temp.write_text("\n".join(lines[-_KEEP:]) + "\n")
        temp.replace(record)
    except OSError as err:
        _notice(f"gate-state: cannot write {record}: {err}")
    return 0


def _read(record: Path) -> list[str]:
    try:
        return [ln for ln in record.read_text().splitlines() if ln.strip()]
    except OSError:
        return []


def green(repo: Path, gate: str) -> str | None:
    """The record line saying HEAD passed `gate`, when the push may skip it; None means run the gate."""
    key = head_key(repo)
    record = _git_path(repo, RECORD, common=True)
    if key is None or record is None:
        return None
    pushed = os.environ.get("PRE_COMMIT_TO_REF", "")
    if pushed and pushed != _git(repo, "rev-parse", "HEAD"):
        return None
    want = [gate, *key.split(" ")]
    return next((ln for ln in _read(record) if ln.split(" ")[:3] == want), None)


def pre_push(repo: Path, gate: str, cmd: Sequence[str]) -> int:
    """Skip `cmd` when HEAD's tree already passed `gate` (see `green`); else exec it."""
    line = green(repo, gate)
    if line is not None:
        tree, when = line.split(" ")[1], line.split(" ")[-1]
        _notice(f"gate-state: tree {tree[:12]} passed `{gate}` at {when}; not run again")
        return 0
    return _exec(cmd, dict(os.environ))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=".", help="the repo (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)
    lock = sub.add_parser("lock", help="run CMD under the box-wide test lock")
    lock.add_argument("cmd", nargs=argparse.REMAINDER, metavar="-- CMD")
    sub.add_parser("start", help="note the working tree as the gate starts")
    done = sub.add_parser("passed", help="record the noted tree as green, if unchanged")
    done.add_argument("--gate", default="check", help="the gate that passed (default: check)")
    push = sub.add_parser("pre-push", help="run CMD unless HEAD's tree is recorded green")
    push.add_argument("--gate", default="check", help="the gate CMD runs (default: check)")
    push.add_argument("cmd", nargs=argparse.REMAINDER, metavar="-- CMD")
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()
    if args.command in {"lock", "pre-push"}:
        cmd = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
        if not cmd:
            parser.error(f"{args.command}: give the command after --")
        return run_locked(cmd) if args.command == "lock" else pre_push(repo, args.gate, cmd)
    if args.command == "start":
        return start(repo)
    return passed(repo, args.gate)


if __name__ == "__main__":
    sys.exit(main())
