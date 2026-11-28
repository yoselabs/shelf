"""One gate at a time: a second gate waits for the slot, says who holds it, never waits forever, and never waits on its own parent."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from typing import TYPE_CHECKING

from any_gate.gate_lease import GATE_LEASE, LEASED_ENV, default_root, hold
from any_lease import Leases

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _hold(
    root: Path, env: dict[str, str] | None = None, *, slots: int = 1, limit: float = 5.0, stale: float | None = None
) -> tuple[dict[str, str], list[str]]:
    said: list[str] = []
    with hold(
        root, slots=slots, wait_limit=limit, label="gate in /me", env=env or {}, say=said.append, poll=0.02, stale_after=stale
    ) as child:
        return child, said


def test_a_free_box_runs_at_once_and_says_nothing(tmp_path: Path) -> None:
    child, said = _hold(tmp_path)
    assert said == []
    assert child[LEASED_ENV] == str(os.getpid())  # the steps' own gates take no second slot while this gate lives


def test_a_busy_box_is_waited_for_with_one_line_naming_the_holder(tmp_path: Path) -> None:
    first = Leases(tmp_path).acquire(GATE_LEASE, 1, label="gate in /other")
    threading.Timer(0.3, first.release).start()
    _, said = _hold(tmp_path)
    assert len(said) == 2
    assert "waiting for a gate slot, held by gate in /other (pid" in said[0]
    assert "got the gate slot after" in said[1]


def test_a_live_fresh_holder_is_waited_for_past_the_limit(tmp_path: Path) -> None:
    first = Leases(tmp_path).acquire(GATE_LEASE, 1, label="gate in /other")
    threading.Timer(0.5, first.release).start()
    _, said = _hold(tmp_path, limit=0.1)
    assert not any("running anyway" in line for line in said)
    assert any("got the gate slot" in line for line in said)


def test_a_stale_holder_is_overridden_at_the_limit(tmp_path: Path) -> None:
    with Leases(tmp_path).acquire(GATE_LEASE, 1, label="hung"):
        child, said = _hold(tmp_path, limit=0.2, stale=0.0)
    assert any("running anyway" in line and "min old" in line for line in said)
    assert child[LEASED_ENV] == str(os.getpid())


def test_a_holder_whose_pid_is_gone_is_overridden(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("any_gate.gate_lease._alive", lambda _pid: False)
    with Leases(tmp_path).acquire(GATE_LEASE, 1, label="orphan"):
        _, said = _hold(tmp_path, limit=0.1)
    assert any("holder is gone" in line for line in said)


def test_a_waiter_in_the_holders_own_repo_is_told_so_at_once(tmp_path: Path) -> None:
    first = Leases(tmp_path).acquire(GATE_LEASE, 1, label="gate in /me")
    threading.Timer(0.2, first.release).start()
    _, said = _hold(tmp_path)
    assert "a gate already runs in this repo" in said[0]


def test_a_flag_left_by_a_dead_gate_waives_nothing(tmp_path: Path) -> None:
    child, said = _hold(tmp_path, {LEASED_ENV: "1"})  # a bare flag from an older gate
    assert child[LEASED_ENV] == str(os.getpid())
    assert said == []
    with Leases(tmp_path).acquire(GATE_LEASE, 1, label="other"):
        _, said = _hold(tmp_path, {LEASED_ENV: "999999999"}, limit=0.1, stale=0.0)
    assert any("running anyway" in line for line in said)  # it queued: the stale flag did not skip the lease


def test_the_lease_root_does_not_follow_a_rewritten_home(tmp_path: Path) -> None:
    real = default_root({})
    assert default_root({"HOME": str(tmp_path)}) == real
    assert default_root({"XDG_CACHE_HOME": str(tmp_path)}) == tmp_path / "gate-leases"
    assert default_root({"GATE_LEASE_ROOT": str(tmp_path / "x")}) == tmp_path / "x"


def test_an_unusable_lease_folder_warns_and_runs(tmp_path: Path) -> None:
    blocked = tmp_path / "file"
    blocked.write_text("not a folder")
    child, said = _hold(blocked / "leases")
    assert any("unusable" in line for line in said)
    assert LEASED_ENV in child


def test_a_gate_inside_a_gate_takes_no_slot_so_it_cannot_wait_on_its_parent(tmp_path: Path) -> None:
    with Leases(tmp_path).acquire(GATE_LEASE, 1, label="parent"):
        mine = {LEASED_ENV: str(os.getpid())}
    child, said = _hold(tmp_path, mine, limit=0.1)
    assert said == []
    assert child == mine


def test_zero_slots_turns_the_lease_off(tmp_path: Path) -> None:
    with Leases(tmp_path).acquire(GATE_LEASE, 1, label="other"):
        _, said = _hold(tmp_path, slots=0, limit=0.1)
    assert said == []


def test_two_slots_let_two_gates_share_the_box(tmp_path: Path) -> None:
    with Leases(tmp_path).acquire(GATE_LEASE, 2, label="one"):
        _, said = _hold(tmp_path, slots=2, limit=0.1)
    assert said == []


def test_the_steps_verb_queues_behind_a_held_slot_and_still_runs(tmp_path: Path) -> None:
    fake = tmp_path / "fake-just"
    fake.write_text('#!/bin/sh\necho "$1" >> "$RUNS"\n')
    fake.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k != LEASED_ENV}
    cmd = [sys.executable, "-m", "any_gate", "steps", "--runner", str(fake), "--lease-root", str(tmp_path / "l"), "--gate-wait", "0.3", "a"]
    with Leases(tmp_path / "l").acquire(GATE_LEASE, 1, label="holder"):
        wanted = {**env, "RUNS": str(tmp_path / "r"), "GATE_STALE_AFTER": "0"}
        done = subprocess.run(cmd, env=wanted, capture_output=True, text=True, check=False, cwd=tmp_path)
    assert done.returncode == 0
    assert "waiting for a gate slot, held by holder" in done.stderr
    assert "running anyway" in done.stderr
    assert (tmp_path / "r").read_text() == "a\n"
