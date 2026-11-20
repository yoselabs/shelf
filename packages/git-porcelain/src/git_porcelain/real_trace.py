"""Which git hooks ran, read from a ``GIT_TRACE2_EVENT`` file."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def trace_hooks(trace: Path) -> tuple[tuple[str, ...], tuple[tuple[str, int], ...]]:
    if not trace.exists():
        return (), ()
    hooks: list[str] = []
    children: dict[tuple[str, int], str] = {}
    exits: list[tuple[str, int]] = []
    for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():  # lossy-ok: parse: JSON trace lines, bad lines skipped
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        child_id, sid = event.get("child_id"), event.get("sid", "")
        if not isinstance(child_id, int) or not isinstance(sid, str):
            continue
        key = (sid, child_id)
        if event.get("event") == "child_start" and event.get("child_class") == "hook":
            name = event.get("hook_name")
            if isinstance(name, str):
                hooks.append(name)
                children[key] = name
        elif event.get("event") == "child_exit" and key in children:
            code = event.get("code")
            if isinstance(code, int):
                exits.append((children.pop(key), code))
    return tuple(hooks), tuple(exits)
