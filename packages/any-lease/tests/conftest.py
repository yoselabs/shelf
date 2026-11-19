"""A test must release every lease it takes: the lock registry is process-wide, so a leak outlives the test.

`process_lock.held()` is the set of lock files this process holds. A test that leaves one held makes any later test in the same
worker (this package's or another's, under xdist) that asserts an empty registry fail, depending on how the run was split.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import process_lock
import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _no_lease_outlives_its_test() -> Iterator[None]:
    before = process_lock.held()
    yield
    leaked = process_lock.held() - before
    assert not leaked, f"the test left these leases held: {sorted(str(p) for p in leaked)}"
