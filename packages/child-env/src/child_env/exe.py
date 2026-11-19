"""Find a program for a child process: one owner of binary discovery.

``find(name, env, extra_dirs)`` searches ``env["PATH"]`` (the injected mapping, never the process environment), then
``extra_dirs`` in order. A miss raises ``NotFound`` naming every folder searched; the bare name is never handed back,
because a bare name sent to ``subprocess`` searches the ambient PATH, the thing this function exists to avoid.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


@dataclass(frozen=True, slots=True)
class Exe:
    """A program that was found: where it is and which search found it."""

    path: Path
    how: Literal["path", "extra_dir"]


class NotFound(LookupError):
    """No executable of that name in any searched folder; ``searched`` lists them in order."""

    def __init__(self, name: str, searched: tuple[str, ...]) -> None:
        self.name = name
        self.searched = searched
        where = ", ".join(searched) if searched else "no folder (empty PATH and no extra_dirs)"
        super().__init__(f"{name!r} not found; searched {where}")


def _is_exe(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def find(name: str, env: Mapping[str, str], extra_dirs: Iterable[Path | str] = ()) -> Exe:
    """The first executable ``name`` in ``env["PATH"]``, then in ``extra_dirs``; ``NotFound`` otherwise.

    ``name`` is a bare program name (a separator raises ``ValueError``). Empty PATH entries are skipped, not read as
    the working folder.
    """
    if os.sep in name or (os.altsep and os.altsep in name):
        message = f"find() takes a bare name, got {name!r}"
        raise ValueError(message)
    on_path = [d for d in env.get("PATH", "").split(os.pathsep) if d]
    extra = [str(d) for d in extra_dirs]
    for how, folders in (("path", on_path), ("extra_dir", extra)):
        for folder in folders:
            candidate = Path(folder) / name
            if _is_exe(candidate):
                return Exe(path=candidate, how=how)
    raise NotFound(name, (*on_path, *extra))
