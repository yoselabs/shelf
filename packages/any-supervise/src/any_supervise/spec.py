"""Read the TOML spec."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from any_supervise.model import Spec, SpecError, Worker

if TYPE_CHECKING:
    from collections.abc import Mapping

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
_TOP = ("state", "version_cmd", "version_cwd", "worker")
_WORKER = ("name", "command", "count", "cwd", "env", "env_pass", "log", "stop_timeout_s")
STOP_TIMEOUT_S = 30.0


def load_spec(path: Path) -> Spec:
    """Parse and validate `path`; relative paths in it resolve against its folder. Raises `SpecError`."""
    path = path.expanduser().resolve()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        msg = f"{path}: {exc}"
        raise SpecError(msg) from exc
    _no_unknown(path, data, _TOP)
    rows = data.get("worker")
    if not isinstance(rows, list) or not rows:
        msg = f"{path}: at least one [[worker]] is required"
        raise SpecError(msg)
    base = path.parent
    workers = tuple(_worker(path, row, base) for row in rows)
    names = [w.name for w in workers] + [f"{w.name}-{i}" for w in workers for i in range(1, w.count + 1)]
    if len(names) != len(set(names)):
        msg = f"{path}: worker and replica names must all differ (a replica is <worker>-<n>)"
        raise SpecError(msg)
    return Spec(
        path=path,
        state=_dir(path, data, "state", base),
        version_cmd=_argv(path, data, "version_cmd"),
        version_cwd=_dir(path, data, "version_cwd", base),
        workers=workers,
    )


def _no_unknown(path: Path, table: Mapping[str, object], allowed: tuple[str, ...]) -> None:
    if unknown := sorted(set(table) - set(allowed)):
        msg = f"{path}: unknown key(s) {unknown}; allowed: {sorted(allowed)}"
        raise SpecError(msg)


def _argv(path: Path, table: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = table.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(a, str) and a for a in value):
        msg = f"{path}: `{key}` must be a non-empty list of non-empty strings"
        raise SpecError(msg)
    return tuple(value)


def _dir(path: Path, table: Mapping[str, object], key: str, base: Path) -> Path:
    value = table.get(key)
    if not isinstance(value, str) or not value:
        msg = f"{path}: `{key}` must be a path string"
        raise SpecError(msg)
    return (base / Path(value).expanduser()).resolve()


def _worker(path: Path, row: object, base: Path) -> Worker:
    if not isinstance(row, dict):
        msg = f"{path}: each [[worker]] is a table"
        raise SpecError(msg)
    _no_unknown(path, row, _WORKER)
    name, count = row.get("name"), row.get("count", 1)
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        msg = f"{path}: worker `name` must match {_NAME.pattern}"
        raise SpecError(msg)
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        msg = f"{path}: worker {name}: `count` must be an integer >= 1"
        raise SpecError(msg)
    env, keep, timeout = row.get("env", {}), row.get("env_pass", []), row.get("stop_timeout_s", STOP_TIMEOUT_S)
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        msg = f"{path}: worker {name}: `env` must be a table of strings"
        raise SpecError(msg)
    if not isinstance(keep, list) or not all(isinstance(k, str) for k in keep):
        msg = f"{path}: worker {name}: `env_pass` must be a list of names or PREFIX* patterns"
        raise SpecError(msg)
    if isinstance(timeout, bool) or not isinstance(timeout, int | float) or timeout < 0:
        msg = f"{path}: worker {name}: `stop_timeout_s` must be a number >= 0"
        raise SpecError(msg)
    return Worker(
        name=name,
        command=_argv(path, row, "command"),
        count=count,
        cwd=_dir(path, {"cwd": row.get("cwd", ".")}, "cwd", base),
        log=_dir(path, row, "log", base),
        env=dict(env),
        env_pass=tuple(keep),
        stop_timeout_s=float(timeout),
    )
