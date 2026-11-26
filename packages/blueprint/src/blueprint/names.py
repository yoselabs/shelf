"""One spelling of a project name: how pyproject, uv.lock and `uv pip list` may each write the same project."""

from __future__ import annotations

import re

_SEPARATORS = re.compile(r"[-_.]+")


def canonical_name(name: str) -> str:
    """PEP 503 normal form: lower case, runs of `-`, `_` and `.` as one `-`."""
    return _SEPARATORS.sub("-", name).lower()
