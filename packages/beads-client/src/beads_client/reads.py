"""The existing read surfaces (one task, the ready set), independent of transport and mutation verbs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from beads_client.records import Bead


class TaskReadClient(Protocol):
    """Read one backend record; only authoritative absence returns None, failures raise BdError."""

    def show(self, task_id: str, /) -> Bead | None:
        """Return the matching record without modifying it or the backlog."""
        ...


class ReadyReadClient(Protocol):
    """Read the tracker's ready set: open, unblocked, undeferred records, in the tracker's own order.

    A label keeps only records carrying it. An empty result is []; any failure raises BdError (never an empty success).
    """

    def ready(self, label: str = "", /) -> list[Bead]:
        """Return the ready records without modifying them or the backlog."""
        ...
