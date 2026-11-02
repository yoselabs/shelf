"""Ordered any-of matching over a consumer's collection of globs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from any_path_glob.glob import Glob

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


@dataclass(frozen=True, init=False)
class GlobSet:
    """Deduplicate by pattern, keeping the first Glob and declaration order."""

    _globs: tuple[Glob, ...]

    def __init__(self, globs: Iterable[str | Glob]) -> None:
        unique = dict.fromkeys(Glob(glob) if isinstance(glob, str) else glob for glob in globs)
        object.__setattr__(self, "_globs", tuple(unique))

    def matches(self, path: str) -> bool:
        return self.first(path) is not None

    def first(self, path: str) -> Glob | None:
        return next((glob for glob in self if glob.matches(path)), None)

    def filter(self, paths: Iterable[str]) -> list[str]:
        return [path for path in paths if self.matches(path)]

    def __contains__(self, path: object) -> bool:
        return isinstance(path, str) and self.matches(path)

    def __iter__(self) -> Iterator[Glob]:
        return iter(self._globs)

    def __len__(self) -> int:
        return len(self._globs)
