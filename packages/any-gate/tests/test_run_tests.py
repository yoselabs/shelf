"""run_tests: pytest in stages (parallel, serial, quarantine) under a wall and an idle limit."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest
from any_gate import run_tests

if TYPE_CHECKING:
    from pathlib import Path


def _project(root: Path, **tests: str) -> Path:
    """A throwaway pytest project: `serial` and `quarantine` markers declared, one test file per keyword."""
    (root / "pytest.ini").write_text("[pytest]\nmarkers =\n    serial: runs alone\n    quarantine: flaky, cannot block\n")
    for name, body in tests.items():
        (root / f"test_{name}.py").write_text(textwrap.dedent(body))
    return root


def _run(root: Path, *paths: str, **kw: object):
    return run_tests(list(paths) or ["."], cwd=root, **kw)  # type: ignore[arg-type]


def test_passing_tests_make_an_ok_outcome(tmp_path: Path) -> None:
    root = _project(tmp_path, a="def test_a():\n    assert True\n")
    outcome = _run(root)
    assert outcome.ok
    assert [s.name for s in outcome.stages] == ["parallel"]


def test_a_failing_test_makes_the_outcome_not_ok(tmp_path: Path) -> None:
    root = _project(tmp_path, a="def test_a():\n    assert False\n")
    outcome = _run(root)
    assert not outcome.ok
    assert outcome.stages[0].returncode == 1


def test_serial_tests_run_after_the_parallel_ones_in_a_stage_of_their_own(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        a="import pytest\n\n@pytest.mark.serial\ndef test_s():\n    assert True\n\ndef test_p():\n    assert True\n",
    )
    outcome = _run(root)
    assert [s.name for s in outcome.stages] == ["parallel", "serial"]
    assert outcome.ok


def test_a_failing_quarantined_test_is_reported_and_never_blocks(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        a="import pytest\n\n@pytest.mark.quarantine\ndef test_flaky():\n    assert False\n\ndef test_fine():\n    assert True\n",
    )
    outcome = _run(root)
    assert outcome.ok
    assert outcome.quarantined_failed
    assert [s.name for s in outcome.stages] == ["parallel", "quarantine"]


def test_a_stage_with_no_tests_is_not_a_failure(tmp_path: Path) -> None:
    # pytest exits 5 when a marker selects nothing; that is how every stage but the first usually ends
    root = _project(tmp_path, a="def test_a():\n    assert True\n")
    assert _run(root).ok


def test_workers_run_the_parallel_stage_across_processes(tmp_path: Path) -> None:
    root = _project(tmp_path, a="def test_a():\n    assert True\n", b="def test_b():\n    assert True\n")
    assert _run(root, workers=2).ok


def test_a_test_that_outlives_the_wall_limit_is_stopped_and_named(tmp_path: Path) -> None:
    root = _project(tmp_path, a="import time\n\ndef test_slow():\n    time.sleep(30)\n")
    outcome = _run(root, wall=1.0)
    assert not outcome.ok
    assert outcome.stages[0].stopped == "wall"


def test_a_run_that_goes_silent_is_stopped_by_the_idle_limit(tmp_path: Path) -> None:
    root = _project(tmp_path, a="import time\n\ndef test_hang():\n    time.sleep(30)\n")
    outcome = _run(root, idle=1.0)
    assert not outcome.ok
    assert outcome.stages[0].stopped == "idle"


def test_the_output_of_every_stage_reaches_the_caller(tmp_path: Path) -> None:
    root = _project(tmp_path, a="def test_a():\n    print('hello from a test')\n")
    lines: list[str] = []
    _run(root, on_output=lines.append, extra=("-s",))
    assert any("hello from a test" in line for line in lines)


@pytest.mark.parametrize("paths", [["test_a.py"], ["."]])
def test_the_paths_are_the_selection(tmp_path: Path, paths: list[str]) -> None:
    root = _project(tmp_path, a="def test_a():\n    assert True\n", b="def test_b():\n    assert False\n")
    assert _run(root, *paths).ok == (paths == ["test_a.py"])
