"""Property-based tests, additive on top of the lifecycle example suite.

See docs/runbooks/property-based-testing.md. The example suite already tests
concurrent `ensure()` at one fixed N=8 and checks the connection object is shared —
this generalizes N, and adds the thing that ISN'T tested: whether `on_open` (schema
setup) runs more than once under the same race. Running it twice against a real
schema statement wouldn't necessarily raise (CREATE TABLE IF NOT EXISTS is
idempotent), so a double-run bug here could hide silently without a property
counting calls directly.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlite_resource import SqliteResource

_IO_SETTINGS = settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@given(n=st.integers(min_value=1, max_value=20))
@_IO_SETTINGS
def test_property_on_open_runs_exactly_once_under_any_concurrency(n: int) -> None:
    """For any number of concurrent first-callers, on_open fires exactly once —
    not "the connection is shared" (already tested), but "setup ran once."
    """
    calls = 0

    async def on_open(_conn: object) -> None:
        nonlocal calls
        calls += 1

    async def run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = SqliteResource(Path(tmp) / "d.sqlite", on_open=on_open)
            conns = await asyncio.gather(*(res.ensure() for _ in range(n)))
            assert all(c is conns[0] for c in conns)
            await res.close()

    asyncio.run(run())
    assert calls == 1


@given(n_closes=st.integers(min_value=1, max_value=10))
@_IO_SETTINGS
def test_property_close_is_idempotent_for_any_number_of_calls(n_closes: int) -> None:
    """Generalizes test_close_is_idempotent beyond exactly two calls."""

    async def run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = SqliteResource(Path(tmp) / "d.sqlite")
            await res.ensure()
            for _ in range(n_closes):
                await res.close()  # must never raise, no matter how many times

    asyncio.run(run())


@given(n_ensures=st.integers(min_value=1, max_value=10))
@_IO_SETTINGS
def test_property_ensure_always_returns_the_same_connection(n_ensures: int) -> None:
    """Generalizes the "first is second" example beyond exactly two sequential calls."""

    async def run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            res = SqliteResource(Path(tmp) / "d.sqlite")
            conns = [await res.ensure() for _ in range(n_ensures)]
            assert all(c is conns[0] for c in conns)
            await res.close()

    asyncio.run(run())
