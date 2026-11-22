"""A counting lease across processes: up to ``limit`` holders of a named resource.

Each unit is one :mod:`process_lock` flock (``<root>/<name>-<slot>.lock``), so the kernel frees a unit when its holder dies,
``kill -9`` included. :meth:`Leases.try_claim` is the one-unit form for a free-form key, and :class:`Pacer` spaces passes
on a key across processes and holds a shared "blocked until" for it. Waiting is a poll; ``cancel`` and ``timeout`` end it with nothing held.
"""

from any_lease.leases import Held, HeldAll, LeaseCancelledError, Leases, LeaseTimeoutError, Occupant, Waiting
from any_lease.pace import Pacer, PaceStatus

__all__ = ["Held", "HeldAll", "LeaseCancelledError", "LeaseTimeoutError", "Leases", "Occupant", "PaceStatus", "Pacer", "Waiting"]
