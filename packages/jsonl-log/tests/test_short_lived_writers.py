"""A process that opens a log, appends one line and exits (the retry-later shape): no line is lost or torn across processes."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING

from jsonl_log import JsonlReader

if TYPE_CHECKING:
    from pathlib import Path

_ONE_SHOT = """
import sys
from pathlib import Path
from jsonl_log import JsonlLog
path, who = Path(sys.argv[1]), sys.argv[2]
for n in range(40):
    with JsonlLog.open(path) as log:
        log.append_json({"who": who, "n": n, "reason": "x" * 300})
"""


def test_processes_that_open_append_and_close_lose_no_line(tmp_path: Path) -> None:
    path = tmp_path / "retry-later.jsonl"
    procs = [
        subprocess.Popen([sys.executable, "-I", "-c", _ONE_SHOT, str(path), who], stderr=subprocess.PIPE, text=True)
        for who in ("a", "b", "c", "d")
    ]
    errors = [p.communicate()[1] for p in procs]
    assert [p.returncode for p in procs] == [0, 0, 0, 0], errors
    rows = list(JsonlReader(path).records(json.loads))
    assert sorted((r["who"], r["n"]) for r in rows) == sorted((w, n) for w in "abcd" for n in range(40))
