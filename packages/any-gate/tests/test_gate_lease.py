"""One gate at a time: a second gate waits for the slot, says who holds it, never waits forever, and never waits on its own parent."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from typing import TYPE_CHECKING

from any_gate.gate_lease import GATE_LEASE, LEASED_ENV, hold
from any_lease import Leases

if TYPE_CHECKING:
    from pathlib import Path


def _hold(root: Path, env: dict[str, str] | None = None, *, slots: int = 1, limit: float = 5.0) -> tuple[dict[str, str], list[str]]:
    said: list[str] = []
    with hold(root, slots=slots, wait_limit=limit, label="gate in /me", env=env or {}, say=said.append, poll=0.02) as child:
        return child, said


def test_a_free_box_runs_at_once_and_says_nothing(tmp_path: Path) -> None:
    child, said = _hold(tmp_path)
    assert said == []
    assert child[LEASED_ENV] == "1"  # the steps' own gates take no second slot


def test_a_busy_box_is_waited_for_with_one_line_naming_the_holder(tmp_path: Path) -> None:
    first = Leases(tmp_path).acquire(GATE_LEASE, 1, label="gate in /other")
    threading.Timer(0.3, first.release).start()
    _, said = _hold(tmp_path)
    assert len(said) == 2
    assert "waiting for a gate slot, held by gate in /other (pid" in said[0]
    assert "got the gate slot after" in said[1]


def test_the_wait_ends_at_its_limit_and_the_gate_runs_anyway(tmp_path: Path) -> None:
    with Leases(tmp_path).acquire(GATE_LEASE, 1, label="hung"):
        child, said = _hold(tmp_path, limit=0.2)
    assert any("running anyway" in line for line in said)
    assert child[LEASED_ENV] == "1"


def test_a_gate_inside_a_gate_takes_no_slot_so_it_cannot_wait_on_its_parent(tmp_path: Path) -> None:
    with Leases(tmp_path).acquire(GATE_LEASE, 1, label="parent"):
        child, said = _hold(tmp_path, {LEASED_ENV: "1"}, limit=0.1)
    assert said == []
    assert child == {LEASED_ENV: "1"}


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
        done = subprocess.run(cmd, env={**env, "RUNS": str(tmp_path / "r")}, capture_output=True, text=True, check=False, cwd=tmp_path)
    assert done.returncode == 0
    assert "waiting for a gate slot, held by holder" in done.stderr
    assert "running anyway" in done.stderr
    assert (tmp_path / "r").read_text() == "a\n"
