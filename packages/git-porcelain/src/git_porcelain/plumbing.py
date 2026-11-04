"""Shared ref records and the path-based plumbing contract (real module or fake)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

    from git_porcelain.api import CommandResult


@dataclass(frozen=True)
class Ref:
    """A ref's name and object id; branch listings use names relative to their namespace."""

    name: str
    oid: str


class Refs(list[Ref]):
    """Path-based remote refs with list behavior and complete command output."""

    def __init__(self, refs: Iterable[Ref] = (), *, output: str = "") -> None:
        super().__init__(refs)
        self.output = output


class Plumbing(Protocol):
    """The functional plumbing surface, implemented by the module and ``FakePlumbing``."""

    def ls_remote(self, repo: Path, remote: str, *patterns: str) -> Refs: ...
    def branches(self, repo: Path, remote: str | None = None) -> list[Ref]: ...
    def delete_ref_at(self, repo: Path, ref: str, oid: str) -> None: ...
    def config_get(self, repo: Path, key: str, default: str | None = None) -> str | None: ...
    def config_entries(self, repo: Path, pattern: str) -> list[tuple[str, str]]: ...
    def symbolic_ref(self, repo: Path, name: str) -> str | None: ...
    def merge_ff(self, repo: Path, ref: str) -> None: ...
    def pull_rebase(self, repo: Path, remote: str, branch: str) -> CommandResult: ...
    def check_ignore(self, repo: Path, paths: Sequence[str]) -> set[str]: ...
    def ls_files(self, repo: Path, *, scope: str = "tracked") -> list[str]: ...
