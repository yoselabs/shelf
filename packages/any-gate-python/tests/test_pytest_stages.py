"""run_tests: pytest in stages (parallel, serial, quarantine) under a wall and an idle limit."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import pytest
from any_gate_python import stages as run_module
from any_gate_python.stages import run_tests

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _run(root: Path, *paths: str, **kw: object):
    return run_tests(list(paths) or ["."], cwd=root, **{"env": os.environ, **kw})  # type: ignore[arg-type]


def test_passing_tests_make_an_ok_outcome(project: Callable[..., Path]) -> None:
    root = project(a="def test_a():\n    assert True\n")
    outcome = _run(root)
    assert outcome.ok
    assert [s.name for s in outcome.stages] == ["parallel"]


def test_a_failing_test_makes_the_outcome_not_ok(project: Callable[..., Path]) -> None:
    root = project(a="def test_a():\n    assert False\n")
    outcome = _run(root)
    assert not outcome.ok
    assert outcome.stages[0].returncode == 1


def test_serial_tests_run_after_the_parallel_ones_in_a_stage_of_their_own(project: Callable[..., Path]) -> None:
    root = project(
        a="import pytest\n\n@pytest.mark.serial\ndef test_s():\n    assert True\n\ndef test_p():\n    assert True\n",
    )
    outcome = _run(root)
    assert [s.name for s in outcome.stages] == ["parallel", "serial"]
    assert outcome.ok


def test_a_failing_quarantined_test_is_reported_and_never_blocks(project: Callable[..., Path]) -> None:
    root = project(
        a="import pytest\n\n@pytest.mark.quarantine\ndef test_flaky():\n    assert False\n\ndef test_fine():\n    assert True\n",
    )
    outcome = _run(root)
    assert outcome.ok
    assert outcome.quarantined_failed
    assert [s.name for s in outcome.stages] == ["parallel", "quarantine"]


def test_a_stage_with_no_tests_is_not_a_failure(project: Callable[..., Path]) -> None:
    # pytest exits 5 when a marker selects nothing; that is how every stage but the first usually ends
    root = project(a="def test_a():\n    assert True\n")
    assert _run(root).ok


def test_workers_run_the_parallel_stage_across_processes(project: Callable[..., Path]) -> None:
    root = project(a="def test_a():\n    assert True\n", b="def test_b():\n    assert True\n")
    assert _run(root, workers=2).ok


def test_a_test_that_outlives_the_wall_limit_is_stopped_and_named(project: Callable[..., Path]) -> None:
    root = project(a="import time\n\ndef test_slow():\n    time.sleep(30)\n")
    outcome = _run(root, wall=1.0)
    assert not outcome.ok
    assert outcome.stages[0].stopped == "wall"


def test_a_run_that_goes_silent_is_stopped_by_the_idle_limit(project: Callable[..., Path]) -> None:
    root = project(a="import time\n\ndef test_hang():\n    time.sleep(30)\n")
    outcome = _run(root, idle=1.0)
    assert not outcome.ok
    assert outcome.stages[0].stopped == "idle"


def test_the_output_of_every_stage_reaches_the_caller(project: Callable[..., Path]) -> None:
    root = project(a="def test_a():\n    print('hello from a test')\n")
    lines: list[str] = []
    _run(root, on_output=lines.append, extra=("-s",))
    assert any("hello from a test" in line for line in lines)


@pytest.mark.parametrize("paths", [["test_a.py"], ["."]])
def test_the_paths_are_the_selection(project: Callable[..., Path], paths: list[str]) -> None:
    root = project(a="def test_a():\n    assert True\n", b="def test_b():\n    assert False\n")
    assert _run(root, *paths).ok == (paths == ["test_a.py"])


def test_the_outcome_counts_the_tests_it_collected(project: Callable[..., Path]) -> None:
    root = project(a="def test_a():\n    assert True\n\ndef test_b():\n    assert True\n")
    assert _run(root).tests == 2


def test_workers_left_to_the_box_run_a_small_selection_in_one_process(
    project: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(a="def test_a():\n    assert True\n")
    commands: list[list[str]] = []
    real = run_module.run_process

    def spy(cmd: list[str], **kw: Any) -> Any:
        commands.append(list(cmd))
        return real(cmd, **kw)

    monkeypatch.setattr(run_module, "run_process", spy)
    assert _run(root, workers=None).ok
    assert commands
    assert all("-n" not in cmd for cmd in commands)  # no worker pool for one test


def test_the_repos_own_marker_default_still_holds_in_every_stage(project: Callable[..., Path]) -> None:
    # A repo that deselects a lane by default (`addopts = -m "not browser"`) must not find it running because of the stages.
    root = project(
        a="import pytest\n\n@pytest.mark.browser\ndef test_needs_a_browser():\n    assert False\n\ndef test_fine():\n    assert True\n",
    )
    (root / "pytest.ini").write_text('[pytest]\nmarkers =\n    serial: s\n    quarantine: q\n    browser: b\naddopts = -m "not browser"\n')
    outcome = _run(root)
    assert outcome.ok
    assert outcome.tests == 1


def test_a_niced_run_starts_pytest_at_that_priority(project: Callable[..., Path]) -> None:
    base = os.nice(0)
    root = project(a=f"import os\n\ndef test_a():\n    assert os.nice(0) == {base + 5}\n")
    assert _run(root, nice=5).ok
    assert not _run(root).ok  # without it pytest keeps the caller's priority, so the same assertion fails
