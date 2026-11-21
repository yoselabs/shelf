"""`any-supervise up|status|roll|down|logs SPEC`: a thin layer over the library. Exit 0 ok, 1 not all running, 2 a failure."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from any_supervise import (
    Host,
    ReplicaStatus,
    State,
    SuperviseError,
    down,
    load_spec,
    logs,
    roll,
    status,
    up,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from any_supervise import Spec


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    host = Host(environ=os.environ)
    try:
        code: int = args.run(args, load_spec(args.spec), host)
    except (SuperviseError, OSError, ExceptionGroup) as exc:
        sys.stderr.write(f"any-supervise: {exc}\n")
        return 2
    return code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="any-supervise", description="Keep a fleet of detached workers honest.")
    sub = parser.add_subparsers(dest="verb", required=True)

    def verb(name: str, text: str, run: Callable[[argparse.Namespace, Spec, Host], int]) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=text, description=text)
        p.add_argument("spec", type=Path, help="the TOML spec")
        p.set_defaults(run=run)
        return p

    verb("up", "Start every missing or dead replica, detached. Idempotent.", _cmd_up)
    p = verb("status", "Show each replica: running, stale, dead, missing or orphan. Exit 1 unless all are running.", _cmd_status)
    p.add_argument("--json", action="store_true", help="print machine-readable JSON")
    p = verb("roll", "Rolling restart of stale replicas (or the named ones), one lane member at a time.", _cmd_roll)
    p.add_argument("--parallel", type=int, default=1, help="replicas in flight at once (default 1)")
    p.add_argument("--settle", type=float, default=3.0, help="seconds a replacement must stay alive (default 3)")
    p.add_argument("names", nargs="*", help="workers or replicas to roll even if not stale")
    p = verb("down", "Gracefully stop what is ours (all, or one worker or replica) and remove its state file.", _cmd_down)
    p.add_argument("name", nargs="?", help="a worker or replica; default every replica")
    p = verb("logs", "Print the tail of one replica's log.", _cmd_logs)
    p.add_argument("name", help="a replica, e.g. snapshots-2")
    p.add_argument("-n", "--lines", type=int, default=50, help="lines to print (default 50)")
    return parser


def _cmd_up(_args: argparse.Namespace, spec: Spec, host: Host) -> int:
    started = up(spec, host)
    for s in started:
        sys.stdout.write(f"started {s.name} pid {s.pid} version {s.version[:12]}\n")
    sys.stdout.write(f"{len(started)} started, {len(spec.replicas) - len(started)} already running\n")
    return 0


def _cmd_status(args: argparse.Namespace, spec: Spec, host: Host) -> int:
    rows = status(spec, host)
    healthy = all(r.state is State.RUNNING for r in rows)
    if args.json:
        sys.stdout.write(json.dumps({"ok": healthy, "replicas": [_row(r) for r in rows]}, indent=2, sort_keys=True) + "\n")
    else:
        for r in rows:
            sys.stdout.write(f"{r.name:<24} {r.state.value.upper() if r.state is State.STALE else r.state.value:<8} pid {r.pid or '-'}\n")
    return 0 if healthy else 1


def _row(r: ReplicaStatus) -> dict[str, object]:
    return {**dataclasses.asdict(r)}


def _cmd_roll(args: argparse.Namespace, spec: Spec, host: Host) -> int:
    done = roll(spec, host, parallel=args.parallel, names=args.names, settle_s=args.settle)
    for r in done:
        sys.stdout.write(f"rolled {r.name}: pid {r.old_pid or '-'} -> {r.new_pid}\n")
    sys.stdout.write(f"{len(done)} rolled\n")
    return 0


def _cmd_down(args: argparse.Namespace, spec: Spec, _host: Host) -> int:
    stopped = down(spec, args.name)
    for s in stopped:
        sys.stdout.write(f"stopped {s.name} pid {s.pid}{'' if s.was_running else ' (was already gone)'}\n")
    return 0


def _cmd_logs(args: argparse.Namespace, spec: Spec, _host: Host) -> int:
    for line in logs(spec, args.name, args.lines):
        sys.stdout.write(line + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
