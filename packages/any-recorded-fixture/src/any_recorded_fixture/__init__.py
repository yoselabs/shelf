"""Recorded JSON exchanges and text goldens, grouped into named cases."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from difflib import unified_diff
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

__all__ = [
    "Case",
    "GoldenMismatchError",
    "cases",
    "golden",
    "read_json",
    "record",
    "scrub",
    "update_requested",
    "write_json",
]


@dataclass
class Case:
    """A recorded case and its metadata."""

    group: str
    case: str
    dir: Path
    meta: dict[str, object]


def read_json(path: Path) -> object:
    """Read a UTF-8 JSON file."""
    return cast("object", json.loads(path.read_text(encoding="utf-8")))


def write_json(path: Path, obj: object) -> None:
    """Write JSON with one-space indentation and a trailing newline."""
    path.write_text(json.dumps(obj, indent=1) + "\n", encoding="utf-8")


def cases(root: Path) -> list[Case]:
    """List group/case directories with meta.json, sorted by group then case."""
    if not root.exists():
        return []
    result: list[Case] = []
    for group in sorted(root.iterdir()):
        if not group.is_dir():
            continue
        for directory in sorted(group.iterdir()):
            if directory.is_dir() and (directory / "meta.json").is_file():
                meta = read_json(directory / "meta.json")
                if not isinstance(meta, dict):
                    message = f"Expected metadata object: {directory / 'meta.json'}"
                    raise ValueError(message)
                result.append(Case(group.name, directory.name, directory, cast("dict[str, object]", meta)))
    return result


def record(
    root: Path,
    group: str,
    case: str,
    files: Mapping[str, object],
    meta: Mapping[str, object],
    *,
    text: Mapping[str, str] | None = None,
) -> Path:
    """Write named JSON and text files, followed by the case metadata."""
    directory = root / group / case
    directory.mkdir(parents=True, exist_ok=True)
    for name, obj in files.items():
        write_json(directory / name, obj)
    for name, content in (text or {}).items():
        (directory / name).write_text(content, encoding="utf-8")
    write_json(directory / "meta.json", dict(meta))
    return directory


class GoldenMismatchError(AssertionError):
    """A golden is missing or differs from actual text."""


def golden(path: Path, actual: str, *, update: bool) -> None:
    """Update a golden explicitly, or compare it and report a unified diff."""
    if update:
        path.write_text(actual, encoding="utf-8")
        return
    missing = False
    try:
        expected = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        expected = ""
        missing = True
    if missing or expected != actual:
        diff = "".join(
            unified_diff(
                expected.splitlines(keepends=True),
                actual.splitlines(keepends=True),
                fromfile=str(path),
                tofile="actual",
            )
        )
        reason = "Missing golden" if missing else "Golden differs"
        message = f"{reason}: {path}\n{diff}"
        raise GoldenMismatchError(message)


def update_requested(env: Mapping[str, str] = os.environ, name: str = "UPDATE_GOLDEN") -> bool:
    """Request an update when the named variable is set and neither empty nor zero."""
    return env.get(name, "") not in ("", "0")


def scrub(text: str, **placeholders: str) -> str:
    """Replace nonempty placeholder values, longest first, with uppercase key tokens."""
    for key, value in sorted(placeholders.items(), key=lambda item: len(item[1]), reverse=True):
        if value:
            text = text.replace(value, f"<{key.upper()}>")
    return text
