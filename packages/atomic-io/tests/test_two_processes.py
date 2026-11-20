"""Two processes writing one path never collide on a temp name (the FileNotFoundError a fixed `.json.tmp` name gave)."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_WRITER = """
import sys
from pathlib import Path
from atomic_io import atomic_write_json
path, who = Path(sys.argv[1]), sys.argv[2]
for n in range(150):
    atomic_write_json(path, {"who": who, "n": n}, fsync=False)
"""


def test_concurrent_writers_all_finish_and_the_file_is_one_whole_write(tmp_path: Path) -> None:
    target = tmp_path / "batch-progress.json"
    procs = [
        subprocess.Popen([sys.executable, "-I", "-c", _WRITER, str(target), who], stderr=subprocess.PIPE, text=True)
        for who in ("a", "b", "c", "d")
    ]
    errors = [p.communicate()[1] for p in procs]
    assert [p.returncode for p in procs] == [0, 0, 0, 0], errors
    final = json.loads(target.read_text(encoding="utf-8"))
    assert final["who"] in {"a", "b", "c", "d"}
    assert final["n"] == 149
    assert [p.name for p in tmp_path.iterdir()] == [target.name]
