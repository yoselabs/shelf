"""Child for the contention test: drain the table, appending each key to a shared log as it runs it.

Run with `python -I`; argv: db_path lease_root log_path.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from any_work import Claimed, Work, drain

db, leases, log = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
work = Work(db, leases)
fd = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT)


async def handler(claimed: Claimed) -> None:
    os.write(fd, f"{claimed.key}\n".encode())  # one small O_APPEND write is atomic across processes
    await asyncio.sleep(0)


asyncio.run(drain(work, handler, concurrency=2, idle_exit_s=0.5, poll_s=0.05))
