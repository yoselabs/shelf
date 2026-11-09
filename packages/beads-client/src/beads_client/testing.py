"""Owning semantic read fake and shared contract; Script separately controls transport replies. No pytest import."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import TYPE_CHECKING

from beads_client.errors import BdError, ErrorKind
from beads_client.records import Bead, Dep
from beads_client.runner import BdRun

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from beads_client.reads import TaskReadClient


class Script:
    """A Runner that answers from a queue (an empty queue answers exit 0, no output) and records every argv."""

    def __init__(self) -> None:
        self.replies: list[BdRun] = []
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], _cwd: str | None) -> BdRun:
        self.calls.append(argv)
        return self.replies.pop(0) if self.replies else BdRun(0, "", "")

    def say(self, out: str = "", err: str = "", code: int = 0) -> Script:
        self.replies.append(BdRun(code, out, err))
        return self


class FakeTaskReadClient:
    """A separate in-memory backlog seeded with records and persistent typed read faults.

    Unknown IDs and explicit not_found faults return None. Other faults take precedence
    over seeded records and raise BdError with their supplied diagnostic fields.
    """

    def __init__(self, records: Iterable[Bead] = (), *, faults: Mapping[str, BdError] | None = None) -> None:
        self._records = {record.id: deepcopy(record) for record in records}
        self._faults = dict(faults or {})
        self.reads: list[str] = []

    def show(self, task_id: str) -> Bead | None:
        self.reads.append(task_id)
        if fault := self._faults.get(task_id):
            if fault.kind == "not_found":
                return None
            raise BdError(fault.kind, fault.text, fault.missing_sections)
        return deepcopy(self._records.get(task_id))


def _expect(actual: object, expected: object) -> None:
    if actual != expected:
        msg = f"expected {expected!r}, got {actual!r}"
        raise AssertionError(msg)


def task_read_contract(make: Callable[[tuple[Bead, ...], Mapping[str, BdError]], TaskReadClient]) -> None:
    """Assert success, authoritative absence, separate backlog instances and typed read failures."""
    record = Bead(
        "read-1",
        title="One task",
        description="  Raw requirements\n\nKeep *meaning*.\n",
        acceptance_criteria="Acceptance\n  stays raw.\n",
        parent="read-parent",
        dependencies=(Dep("read-0", "blocks", "Earlier", "closed"), Dep("read-parent", "parent-child")),
    )
    client = make((record, Bead("read-empty")), {})
    _expect(client.show(record.id), record)
    _expect(client.show("read-empty"), Bead("read-empty"))
    _expect(client.show("read-absent"), None)
    _expect(client.show(record.id), record)
    other = replace(record, description="A different configured backlog")
    _expect(make((other,), {}).show(record.id), other)
    _expect(client.show(record.id), record)
    _expect(make((record,), {record.id: BdError("not_found", f"Issue {record.id} not found")}).show(record.id), None)
    kinds: tuple[ErrorKind, ...] = ("malformed", "missing_binary", "timeout", "other")
    for kind in kinds:
        fault = BdError(kind, f"read failed: {kind}")
        failed = make((record,), {record.id: fault})
        try:
            failed.show(record.id)
        except BdError as error:
            _expect(error.kind, kind)
            if not error.text:
                msg = f"{kind} lost its diagnostic text"
                raise AssertionError(msg) from error
        else:
            msg = f"{kind} became a successful or absent read"
            raise AssertionError(msg)
