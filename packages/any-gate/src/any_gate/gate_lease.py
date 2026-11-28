"""One gate at a time on a box: a second `any-gate steps` waits for the first instead of piling its steps on the same cores.

Overlapping gates in separate worktrees drove the load to 95-160 on a 14-core Mac (every file open is also scanned by the antivirus).
The wait is named in one line (who holds the slot, since when), repeated every `REPEAT_WAIT_NOTICE` seconds, and it ends: after
`WAIT_LIMIT` seconds the gate runs anyway and says so (a hung holder must never hang every other gate). A gate run by a gate (its
steps' children, a test that starts `steps`) inherits `ANY_GATE_LEASED` and takes no second slot, so it cannot wait on its own parent.
The slot is a flock (`any_lease`): the kernel frees it when its holder dies, kill -9 included.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

from any_lease import Leases, LeaseTimeoutError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping
    from pathlib import Path

    from any_lease import Waiting

__all__ = ["GATE_LEASE", "LEASED_ENV", "REPEAT_WAIT_NOTICE", "WAIT_LIMIT", "hold", "wait_message"]

GATE_LEASE = "gate"
LEASED_ENV = "ANY_GATE_LEASED"
WAIT_LIMIT = 900.0  # seconds a gate queues for the box before it runs anyway
REPEAT_WAIT_NOTICE = 300.0  # seconds between "still waiting" notices: a hung holder shows as a growing age, not as silence


def wait_message(wait: Waiting, *, what: str = "test slot", now: float | None = None) -> str:
    """Who holds the slot, since when, and how to free it: a holder that hangs never releases (the kernel frees only a dead one)."""
    holder = wait.occupants[0].holder if wait.occupants else None
    if holder is None:
        return f"waiting for a {what}, held by an unnamed run"
    age = (time.time() if now is None else now) - holder.created if holder.created else None
    held = f", held for {age / 60:.0f} min" if age is not None else ""
    hint = f"; if it hangs (no output, idle CPU): kill {holder.pid}" if age is not None and age > 600 else ""
    return f"waiting for a {what}, held by {holder.label or 'an unnamed run'} (pid {holder.pid}{held}){hint}"


@contextmanager
def hold(
    root: Path,
    *,
    slots: int,
    wait_limit: float,
    label: str,
    env: Mapping[str, str],
    say: Callable[[str], None],
    poll: float = 0.5,
) -> Iterator[dict[str, str]]:
    """Hold one of `slots` gate slots for the block; yields the environment the gate's steps run in.

    No slot is taken when `slots` is 0 or `env` says an enclosing gate holds one. After `wait_limit` seconds in the queue the block
    runs without a slot (and says so).
    """
    child = {**env, LEASED_ENV: "1"}
    if slots <= 0 or env.get(LEASED_ENV):
        yield dict(env)
        return
    told = -1.0

    def waiting(wait: Waiting) -> None:
        nonlocal told
        if told < 0 or wait.elapsed - told >= REPEAT_WAIT_NOTICE:
            told = wait.elapsed
            say(f"gate: {wait_message(wait, what='gate slot')}; runs anyway after {wait_limit:.0f}s")

    try:
        held = Leases(root).acquire(GATE_LEASE, slots, timeout=wait_limit, label=label, on_wait=waiting, poll=poll)
    except LeaseTimeoutError:
        say(f"gate: no gate slot after {wait_limit:.0f}s: running anyway, the box is shared")
        yield child
        return
    with held:
        if held.waited > 0:  # it queued, so a waiting line was said: say the wait is over
            say(f"gate: got the gate slot after {held.waited:.1f}s")
        yield child
