"""The fake bare remote a ``FakeRepo`` fetches from and pushes to."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from git_porcelain.fake_ops import branch_ref
from git_porcelain.fake_store import RepoState

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["FakeRemote"]


class FakeRemote:
    """A bare repository a :class:`FakeRepo` can fetch from and push to."""

    def __init__(self, url: str, *, default_branch: str = "main") -> None:
        self.url = url
        self.default_branch = default_branch
        self.state = RepoState(common=Path(url), default_branch=default_branch)

    @property
    def offline(self) -> bool:
        return self.state.offline

    @offline.setter
    def offline(self, value: bool) -> None:
        self.state.offline = value

    def branches(self) -> dict[str, str]:
        """Branch name to commit sha."""
        return {r.removeprefix("refs/heads/"): s for r, s in self.state.refs.items() if r.startswith("refs/heads/")}

    def advance(self, branch: str, files: Mapping[str, str | None], message: str = "advance") -> str:
        """Someone else pushed: a new commit on ``branch`` writing ``files`` (None deletes a path). Returns its sha."""
        ref = branch_ref(branch)
        tip = self.state.refs.get(ref)
        tree: dict[str, str] = dict(self.state.store.commits[tip].files) if tip else {}
        for path, text in files.items():
            if text is None:
                tree.pop(path, None)
            else:
                tree[path] = self.state.store.put_blob(text.encode())
        made = self.state.store.put_commit(tree, (tip,) if tip else (), message, self.state.tick())
        self.state.refs[ref] = made.sha
        return made.sha
