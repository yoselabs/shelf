"""The type-level guarantees, checked by running pyrefly on programs that must be rejected (and one that must not)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import any_pipeline

_FIXTURE = Path(__file__).parent / "fixtures" / "wrong_programs.txt"
_MARK = re.compile(r"# ERROR (?P<code>[a-z-]+)\s*$")


def _pyrefly(tmp_path: Path) -> list[tuple[int, str]]:
    source = tmp_path / "wrong_programs.py"
    source.write_text(_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    config = tmp_path / "pyrefly.toml"
    src = Path(any_pipeline.__file__).parent.parent
    config.write_text(
        f'preset = "strict"\npython-version = "3.12"\nsearch-path = ["{src}"]\nproject-includes = ["{source}"]\n', encoding="utf-8"
    )
    done = subprocess.run(
        [sys.executable, "-m", "pyrefly", "check", "--config", str(config), "--output-format", "json", str(source)],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    return [(e["line"], e["name"]) for e in json.loads(done.stdout)["errors"]]


def test_each_wrong_program_is_rejected_with_its_code_and_nothing_else_is(tmp_path: Path) -> None:
    expected = []
    for number, line in enumerate(_FIXTURE.read_text(encoding="utf-8").splitlines(), 1):
        if marked := _MARK.search(line):
            expected.append((number, marked["code"]))
    assert len(expected) == 6
    assert sorted(_pyrefly(tmp_path)) == sorted(expected)
