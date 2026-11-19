"""A failure record beside the output, keyed to the audio file: skipped until the file changes."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from any_clock import utc_stamp
from atomic_io import atomic_write_json

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class Failure:
    error: str
    audio_size: int
    audio_mtime_ns: int
    at: str


def record_path(out: Path) -> Path:
    return out.with_name(out.name + ".failed.json")


def record(out: Path, audio: Path, error: Exception) -> None:
    stat = audio.stat()
    at = utc_stamp(datetime.now(UTC))
    failure = Failure(repr(error)[:500], stat.st_size, stat.st_mtime_ns, at)
    atomic_write_json(record_path(out), asdict(failure), indent=1)


def is_known_failure(out: Path, audio: Path) -> bool:
    """True when this exact audio file (size and mtime) already failed; a changed file is tried again."""
    try:
        raw = json.loads(record_path(out).read_text(encoding="utf-8"))
        stat = audio.stat()
    except (OSError, ValueError):
        return False
    return bool(raw.get("audio_size") == stat.st_size and raw.get("audio_mtime_ns") == stat.st_mtime_ns)
