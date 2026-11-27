"""`any-gate steps --opens`: each step's Python file opens and process starts, counted by an audit hook, the busiest step first."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING

import pytest
from any_gate import opens

if TYPE_CHECKING:
    from pathlib import Path

_STEPS = {
    "quiet": f'{sys.executable} -c "pass"',
    "busy": f"""{sys.executable} -c "
import subprocess, sys
for _ in range(20):
    open(sys.argv[0] if sys.argv[0] != '-c' else '/dev/null').close()
subprocess.run([sys.executable, '-c', 'pass'], check=True)"
""",
}


@pytest.fixture
def fake(tmp_path: Path) -> str:
    cases = "".join(f"  {name}) {body} ;;\n" for name, body in _STEPS.items())
    path = tmp_path / "fake-just"
    path.write_text(f'#!/bin/sh\ncase "$1" in\n{cases}esac\n')
    path.chmod(0o755)
    return str(path)


def test_the_report_names_the_busiest_step_first_with_its_opens_and_spawns(fake: str) -> None:
    cmd = [sys.executable, "-m", "any_gate", "steps", "--runner", fake, "--opens", "quiet", "busy"]
    done = subprocess.run(cmd, capture_output=True, text=True, check=False, env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"})
    assert done.returncode == 0, done.stderr
    report = [line for line in done.stderr.splitlines() if line.startswith("gate opens: ") and "opens ·" in line]
    assert report[0].startswith("gate opens: busy ")
    busy = int(report[0].split()[3])
    quiet = int(report[1].split()[3])
    assert busy >= quiet + 20  # twenty opens of its own, on top of the interpreter's imports
    assert "1 spawns" in report[0]  # the one child it started
    assert "2 python procs" in report[0]  # itself and the child
    assert "not counted" in done.stderr


def test_without_the_flag_nothing_is_counted(fake: str) -> None:
    done = subprocess.run(
        [sys.executable, "-m", "any_gate", "steps", "--runner", fake, "quiet"], capture_output=True, text=True, check=False
    )
    assert "gate opens" not in done.stderr


def test_collect_sums_every_process_of_a_step_and_lists_a_silent_step_with_zeros(tmp_path: Path) -> None:
    (tmp_path / "a.opens").write_text(
        textwrap.dedent("""\
        1 10 2
        2 5 0
        """)
    )
    got = opens.collect(tmp_path, ["a", "b"])
    assert got == [opens.Opens("a", 15, 2, 2), opens.Opens("b", 0, 0, 0)]
