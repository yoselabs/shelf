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

    from beads_client.reads import ReadyReadClient, TaskReadClient


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
    `ready` names the seeded records the tracker reports ready, in its order: the fake seeds
    readiness and never computes it. Per-id faults apply to show only; `ready_fault` fails every ready read.
    """

    def __init__(
        self,
        records: Iterable[Bead] = (),
        *,
        faults: Mapping[str, BdError] | None = None,
        ready: Iterable[str] = (),
        ready_fault: BdError | None = None,
    ) -> None:
        self._records = {record.id: deepcopy(record) for record in records}
        self._faults = dict(faults or {})
        self._ready = tuple(ready)
        if unknown := [task_id for task_id in self._ready if task_id not in self._records]:
            msg = f"ready ids must be seeded records: {unknown}"
            raise ValueError(msg)
        if len(set(self._ready)) != len(self._ready):
            msg = f"ready ids must be unique: {list(self._ready)}"
            raise ValueError(msg)
        self._ready_fault = ready_fault
        self.reads: list[str] = []
        self.ready_reads: list[str] = []

    def show(self, task_id: str) -> Bead | None:
        self.reads.append(task_id)
        if fault := self._faults.get(task_id):
            if fault.kind == "not_found":
                return None
            raise BdError(fault.kind, fault.text, fault.missing_sections)
        return deepcopy(self._records.get(task_id))

    def ready(self, label: str = "") -> list[Bead]:
        """Snapshots of the seeded ready records carrying `label` (all when empty), in seeded order."""
        self.ready_reads.append(label)
        if fault := self._ready_fault:
            raise BdError(fault.kind, fault.text, fault.missing_sections)
        rows = (self._records[task_id] for task_id in self._ready)
        return [deepcopy(record) for record in rows if not label or label in record.labels]


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


def _expect_failure(read: Callable[[], object], kind: ErrorKind) -> None:
    try:
        read()
    except BdError as error:
        _expect(error.kind, kind)
        if not error.text:
            msg = f"{kind} lost its diagnostic text"
            raise AssertionError(msg) from error
    else:
        msg = f"{kind} became a successful read"
        raise AssertionError(msg)


def ready_read_contract(
    make: Callable[[tuple[Bead, ...], tuple[str, ...], BdError | None], ReadyReadClient],
) -> None:
    """Assert order, label filtering, empty results, decoded scheduling fields and typed failures."""
    first = Bead("r-3", title="Third id, first in line", status="open", issue_type="task", priority=2, labels=("auto",))
    second = Bead("r-1", issue_type="bug", priority=0, assignee="worker-1", labels=("auto", "shelf"), parent="r-epic")
    third = Bead("r-2", issue_type="feature", priority=1, labels=("manual",))
    waiting = Bead("r-0", status="open", issue_type="task", priority=0, labels=("auto",))
    plain = Bead("r-plain")
    records = (waiting, third, first, second, plain)
    client = make(records, (first.id, second.id, third.id), None)
    _expect(client.ready(), [first, second, third])
    _expect(client.ready("auto"), [first, second])
    _expect(client.ready("absent-label"), [])
    _expect([record.priority for record in make(records, (plain.id,), None).ready()], [None])
    _expect(make(records, (), None).ready(), [])
    _expect(make((third, plain), (plain.id, third.id), None).ready(), [plain, third])
    _expect(client.ready(), [first, second, third])
    kinds: tuple[ErrorKind, ...] = ("malformed", "missing_binary", "timeout", "other")
    for kind in kinds:
        _expect_failure(make(records, (first.id,), BdError(kind, f"ready failed: {kind}")).ready, kind)
