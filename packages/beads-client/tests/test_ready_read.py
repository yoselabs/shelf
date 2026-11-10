"""The owning ready-set read contract, shared by the semantic fake and Bd's real decoder."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING

import pytest

from beads_client import Bd, BdError, Bead, ReadyReadClient
from beads_client.runner import BdRun
from beads_client.testing import FakeTaskReadClient, ready_read_contract

if TYPE_CHECKING:
    from collections.abc import Callable


def _real(records: tuple[Bead, ...], ready_ids: tuple[str, ...], fault: BdError | None) -> ReadyReadClient:
    by_id = {record.id: record for record in records}

    def run(argv: list[str], cwd: str | None) -> BdRun:
        label = argv[argv.index("--label") + 1] if "--label" in argv else ""
        assert argv == ["bd", "--actor", "reader", "ready", "-n", "0", *(["--label", label] if label else []), "--json"]
        assert cwd == "/configured/backlog"
        if fault:
            if fault.kind == "malformed":
                return BdRun(0, "{}", "")
            return BdRun({"timeout": 124, "missing_binary": 127}.get(fault.kind, 1), "", fault.text)
        rows = [asdict(by_id[i]) for i in ready_ids if not label or label in by_id[i].labels]
        # bd prints nothing for an empty ready set
        return BdRun(0, json.dumps(rows) if rows else "", "")

    return Bd("reader", cwd="/configured/backlog", exe="bd", run=run)


def _fake(records: tuple[Bead, ...], ready_ids: tuple[str, ...], fault: BdError | None) -> ReadyReadClient:
    return FakeTaskReadClient(records, ready=ready_ids, ready_fault=fault)


@pytest.mark.parametrize("make", [_real, _fake], ids=["bd", "semantic-fake"])
def test_ready_reads_share_order_filter_and_failure_contracts(
    make: Callable[[tuple[Bead, ...], tuple[str, ...], BdError | None], ReadyReadClient],
) -> None:
    ready_read_contract(make)


def test_fake_records_ready_labels_apart_from_show_ids() -> None:
    fake = FakeTaskReadClient((Bead("a-1", labels=("auto",)),), ready=("a-1",))
    assert [record.id for record in fake.ready()] == ["a-1"]
    assert fake.ready("manual") == []
    assert fake.ready_reads == ["", "manual"]
    assert fake.reads == []


def test_fake_ready_returns_snapshots() -> None:
    record = Bead("a-1", metadata={"source": "original"})
    fake = FakeTaskReadClient((record,), ready=("a-1",))
    record.metadata["source"] = "outside mutation"
    [read] = fake.ready()
    read.metadata["source"] = "read-result mutation"
    assert fake.ready() == [Bead("a-1", metadata={"source": "original"})]


@pytest.mark.parametrize("ready", [("a-2",), ("a-1", "a-1")], ids=["unknown", "duplicate"])
def test_fake_refuses_ready_ids_that_are_not_one_seeded_record(ready: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="ready ids"):
        FakeTaskReadClient((Bead("a-1"),), ready=ready)


def test_fake_show_faults_do_not_hide_a_record_from_ready() -> None:
    fake = FakeTaskReadClient((Bead("a-1"),), faults={"a-1": BdError("timeout", "slow")}, ready=("a-1",))
    assert fake.ready() == [Bead("a-1")]
    with pytest.raises(BdError):
        fake.show("a-1")


def test_fake_ready_fault_persists_with_its_details() -> None:
    fault = BdError("lint", "ready refused", ("Acceptance",))
    fake = FakeTaskReadClient((Bead("a-1"),), ready=("a-1",), ready_fault=fault)
    for _ in range(2):
        with pytest.raises(BdError) as caught:
            fake.ready("auto")
        assert caught.value is not fault
        assert (caught.value.kind, caught.value.text, caught.value.missing_sections) == ("lint", "ready refused", ("Acceptance",))
