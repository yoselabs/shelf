"""One small JSON file per replica in the state folder; a file is the claim "this process is ours"."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from atomic_io import atomic_write_json

from any_supervise.model import Record, StateError

if TYPE_CHECKING:
    from pathlib import Path

    from any_supervise.model import Spec


def path_of(spec: Spec, name: str) -> Path:
    return spec.state / f"{name}.json"


def names(spec: Spec) -> tuple[str, ...]:
    """Every replica name with a state file, in or out of the spec, sorted."""
    return tuple(sorted(p.stem for p in spec.state.glob("*.json")))


def read(spec: Spec, name: str) -> Record | None:
    """The record of `name`, or None when it has no state file. A file that cannot be trusted raises `StateError`."""
    path = path_of(spec, name)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        data = json.loads(raw)
        pid, start, argv = data["pid"], data["start"], data["argv"]
        version, started_at = data["version"], data["started_at"]
    except (ValueError, KeyError, TypeError) as exc:
        msg = f"{path}: not a replica state file ({exc!r})"
        raise StateError(msg) from exc
    ok = isinstance(pid, int) and pid > 1 and isinstance(start, str) and start and isinstance(version, str)
    if not ok or not isinstance(argv, list) or not isinstance(started_at, int | float):
        msg = f"{path}: pid, start, argv, version or started_at is missing or of the wrong type; it is never signalled"
        raise StateError(msg)
    return Record(name, pid, start, tuple(str(a) for a in argv), version, float(started_at))


def write(spec: Spec, record: Record) -> None:
    atomic_write_json(
        path_of(spec, record.name),
        {
            "name": record.name,
            "pid": record.pid,
            "start": record.start,
            "argv": list(record.argv),
            "version": record.version,
            "started_at": record.started_at,
        },
        indent=2,
        sort_keys=True,
    )


def remove(spec: Spec, name: str) -> None:
    path_of(spec, name).unlink()
