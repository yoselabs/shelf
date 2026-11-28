"""One gate at a time on a box: a second `any-gate steps` waits for the first instead of piling its steps on the same cores.

Overlapping gates in separate worktrees drove the load to 95-160 on a 14-core Mac (every file open is also scanned by the antivirus).
The wait is named at once (who holds the slot, since when; on a tty and, when stderr is captured as under a git hook, on /dev/tty),
repeated every `REPEAT_WAIT_NOTICE` seconds. A live holder is waited for as long as it lives: every `WAIT_LIMIT` seconds the gate
re-judges it and runs anyway only when the holder is dead (its pid is gone: a child kept the flock), unnamed, or older than
`STALE_AFTER` (a hung gate must not hang every other one). The slot is a flock (`any_lease`): the kernel frees it when its holder
dies, kill -9 included. A gate run by a gate takes no second slot: `ANY_GATE_LEASED` holds the pid of the gate that owns the slot
and counts only while that pid lives, so a daemon a step started cannot waive the lease of a later, unrelated gate.
"""

from __future__ import annotations

import os
import pwd
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from any_lease import Leases, LeaseTimeoutError
from stream_proc import alive

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Mapping

    from any_lease import Waiting

__all__ = ["GATE_LEASE", "LEASED_ENV", "REPEAT_WAIT_NOTICE", "STALE_AFTER", "WAIT_LIMIT", "default_root", "hold", "wait_message"]

GATE_LEASE = "gate"
LEASED_ENV = "ANY_GATE_LEASED"
WAIT_LIMIT = 900.0  # seconds between re-judgements of a live holder (it is waited for, not overrun)
STALE_AFTER = 7200.0  # a holder older than this is hung (the step limit is 3600): run anyway
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


def default_root(env: Mapping[str, str]) -> Path:
    """`$GATE_LEASE_ROOT`, else `$XDG_CACHE_HOME/gate-leases`, else the account's own `~/.cache/gate-leases`: never `$HOME` alone,
    which an agent sandbox rewrites (two gates on one box would then share no lock)."""
    if env.get("GATE_LEASE_ROOT"):
        return Path(env["GATE_LEASE_ROOT"])
    if env.get("XDG_CACHE_HOME"):
        return Path(env["XDG_CACHE_HOME"]) / "gate-leases"
    return Path(pwd.getpwuid(os.getuid()).pw_dir) / ".cache" / "gate-leases"


def _enclosing(env: Mapping[str, str]) -> bool:
    """True when `ANY_GATE_LEASED` names a live gate: a value left behind by a dead one (or a bare `1`) waives nothing."""
    value = env.get(LEASED_ENV, "")
    return value.isdigit() and int(value) > 1 and alive(int(value))


def _visible(say: Callable[[str], None]) -> Callable[[str], None]:
    """`say`, and when stderr is not a terminal (a git hook captures it) the controlling terminal too, best effort."""

    def both(line: str) -> None:
        say(line)
        if not sys.stderr.isatty():
            try:
                with open("/dev/tty", "w", encoding="utf-8") as tty:  # noqa: PTH123
                    tty.write(line + "\n")
            except OSError:
                pass

    return both


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
    stale_after: float | None = None,
) -> Generator[dict[str, str]]:
    """Hold one of `slots` gate slots for the block; yields the environment the gate's steps run in.

    No slot is taken when `slots` is 0 or `env` names a live enclosing gate. A live, fresh holder is waited for; every `wait_limit`
    seconds it is judged again, and the block runs without a slot (and says so) only once the holder is dead, unnamed or older than
    `stale_after`. A lease folder that cannot be used warns and runs.
    """
    if slots <= 0 or _enclosing(env):
        yield dict(env)
        return
    child = {**env, LEASED_ENV: str(os.getpid())}
    stale_after = float(env.get("GATE_STALE_AFTER") or STALE_AFTER) if stale_after is None else stale_after
    say = _visible(say)
    told = -1.0
    latest: list[Waiting] = []

    def waiting(wait: Waiting) -> None:
        nonlocal told
        latest[:] = [wait]
        if told < 0 or wait.elapsed - told >= REPEAT_WAIT_NOTICE:
            told = wait.elapsed
            holder = wait.occupants[0].holder if wait.occupants else None
            mine = holder is not None and holder.label == label
            lead = "a gate already runs in this repo: " if mine else ""
            held_by = wait_message(wait, what="gate slot")
            say(f"gate: {lead}{held_by}; waited for while alive, overridden when dead or past {stale_after:.0f}s")

    leases = Leases(root)
    while True:
        try:
            held = leases.acquire(GATE_LEASE, slots, timeout=wait_limit, label=label, on_wait=waiting, poll=poll)
            break
        except LeaseTimeoutError as timeout:
            holder = timeout.occupants[0].holder if timeout.occupants else None
            age = time.time() - holder.created if holder is not None and holder.created else 0.0
            if holder is None or not alive(holder.pid) or age > stale_after:
                why = "its holder is gone" if holder is None or not alive(holder.pid) else f"its holder is {age / 60:.0f} min old"
                say(f"gate: no gate slot after {wait_limit:.0f}s and {why}: running anyway, the box is shared")
                yield child
                return
            continue  # a live, fresh holder: keep queuing (waiting() repeats the notice)
        except OSError as error:
            say(f"gate: the lease folder {root} is unusable ({error}): running without a slot")
            yield child
            return
    with held:
        if held.waited > 0:  # it queued, so a waiting line was said: say the wait is over
            say(f"gate: got the gate slot after {held.waited:.1f}s")
        yield child
