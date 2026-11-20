"""Child for the process tests: claim one item, say what happened, then hold it until stdin closes.

Run with `python -I`; argv: db_path lease_root.
"""

from __future__ import annotations

import sys
from pathlib import Path

from any_work import Work

work = Work(Path(sys.argv[1]), Path(sys.argv[2]))
claimed = work.claim()
print(f"CLAIMED {claimed.key}" if claimed else "NONE", flush=True)
sys.stdin.read()
