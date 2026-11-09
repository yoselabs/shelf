"""The existing single-task read surface, independent of transport and mutation verbs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from beads_client.records import Bead


class TaskReadClient(Protocol):
    """Read one backend record; only authoritative absence returns None, failures raise BdError."""

    def show(self, task_id: str, /) -> Bead | None:
        """Return the matching record without modifying it or the backlog."""
        ...
