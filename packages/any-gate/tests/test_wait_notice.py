"""The waiter says who holds the slot and for how long; a long hold gets a kill hint (a hung holder never releases)."""

from __future__ import annotations

from dataclasses import dataclass

from any_gate.cli import wait_message
from any_lease import Occupant, Waiting


@dataclass(frozen=True)
class Holder:
    """The three fields of a lock holder's record that the message reads (process-lock's Holder is not a dependency here)."""

    pid: int
    created: float
    label: str


def _wait(holder: Holder | None) -> Waiting:
    occupants = (Occupant(0, holder),)  # type: ignore[arg-type]  # a stand-in with the fields the message reads if holder else ()
    return Waiting("gate-test", 1, 5.0, occupants)


def test_a_fresh_hold_names_label_pid_and_age() -> None:
    text = wait_message(_wait(Holder(pid=42, created=1000.0, label="gate in /r")), now=1060.0)
    assert "gate in /r" in text
    assert "pid 42" in text
    assert "held for 1 min" in text
    assert "kill" not in text


def test_a_long_hold_says_how_to_free_it() -> None:
    text = wait_message(_wait(Holder(pid=42, created=1.0, label="a2kay")), now=3 * 3600.0 + 1.0)
    assert "held for 180 min" in text
    assert "kill 42" in text


def test_an_unreadable_holder_is_still_named_unnamed() -> None:
    assert "unnamed run" in wait_message(_wait(None))
