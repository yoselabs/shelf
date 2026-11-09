"""The owning single-task read contract, shared by the semantic fake and Bd's real decoder."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING

import pytest

from beads_client import Bd, BdError, Bead, TaskReadClient
from beads_client.runner import BdRun
from beads_client.testing import FakeTaskReadClient, task_read_contract

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


def _real(records: tuple[Bead, ...], faults: Mapping[str, BdError]) -> TaskReadClient:
    by_id = {record.id: record for record in records}

    def run(argv: list[str], cwd: str | None) -> BdRun:
        assert argv[:4] == ["bd", "--actor", "reader", "show"]
        assert argv[5:] == ["--json"]
        assert cwd == "/configured/backlog"
        task_id = argv[4]
        if fault := faults.get(task_id):
            if fault.kind == "malformed":
                return BdRun(0, "[]", "")
            code = {"timeout": 124, "missing_binary": 127}.get(fault.kind, 1)
            return BdRun(code, "", fault.text)
        record = by_id.get(task_id)
        return BdRun(0, json.dumps([asdict(record)]), "") if record else BdRun(1, "", f"Issue {task_id} not found")

    return Bd("reader", cwd="/configured/backlog", exe="bd", run=run)


def _fake(records: tuple[Bead, ...], faults: Mapping[str, BdError]) -> TaskReadClient:
    return FakeTaskReadClient(records, faults=faults)


@pytest.mark.parametrize("make", [_real, _fake], ids=["bd", "semantic-fake"])
def test_single_task_reads_share_success_absence_and_failure_contracts(
    make: Callable[[tuple[Bead, ...], Mapping[str, BdError]], TaskReadClient],
) -> None:
    task_read_contract(make)


def test_fake_records_the_requested_ids_without_a_transport() -> None:
    fake = FakeTaskReadClient((Bead("a-1", description="requirements"),))
    assert fake.show("a-1") is not None
    assert fake.show("a-2") is None
    assert fake.reads == ["a-1", "a-2"]


def test_fake_keeps_record_snapshots_and_persistent_typed_fault_details() -> None:
    record = Bead("a-1", metadata={"source": "original"})
    fault = BdError("malformed", "invalid dependency", ("Dependency details",))
    fake = FakeTaskReadClient((record,), faults={"broken": fault})
    record.metadata["source"] = "outside mutation"
    shown = fake.show(record.id)
    assert shown is not None
    assert shown.metadata == {"source": "original"}
    shown.metadata["source"] = "read-result mutation"
    assert fake.show(record.id) == Bead("a-1", metadata={"source": "original"})
    for _ in range(2):
        with pytest.raises(BdError) as caught:
            fake.show("broken")
        assert (caught.value.kind, caught.value.text, caught.value.missing_sections) == (fault.kind, fault.text, fault.missing_sections)
