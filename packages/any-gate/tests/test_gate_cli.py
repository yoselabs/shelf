"""`python -m any_gate test`: plan lines in, suites with a receipt skipped, the rest run under a lease, receipts written on green."""

from __future__ import annotations

import io
import threading
import time
from typing import TYPE_CHECKING

from any_gate.cli import main
from any_lease import Leases

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import pytest

PASS = "def test_ok():\n    assert True\n"
FAIL = "def test_bad():\n    assert False\n"
COUNT = "from pathlib import Path\n\ndef test_ran():\n    Path('ran.log').open('a').write('x')\n"


def _go(root: Path, plan: str, *args: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    receipts = root / "receipts.json"
    code = main(
        ["test", "--receipts", str(receipts), "--lease-root", str(root / "leases"), "--cwd", str(root), *args],
        stdin=io.StringIO(plan),
    )
    out = capsys.readouterr()
    return code, out.out, out.err


def _runs(root: Path) -> int:
    log = root / "ran.log"
    return len(log.read_text()) if log.exists() else 0


def test_a_suite_runs_and_its_green_result_is_not_run_again_under_the_same_key(
    project: Callable[..., Path], capsys: pytest.CaptureFixture[str]
) -> None:
    root = project(a=COUNT)
    assert _go(root, "test_a.py\tk1\n", capsys=capsys)[0] == 0
    assert _runs(root) == 1
    code, _out, err = _go(root, "test_a.py\tk1\n", capsys=capsys)
    assert (code, _runs(root)) == (0, 1)
    assert "1 suite(s) skipped" in err


def test_a_changed_key_runs_the_suite_again(project: Callable[..., Path], capsys: pytest.CaptureFixture[str]) -> None:
    root = project(a=COUNT)
    _go(root, "test_a.py\tk1\n", capsys=capsys)
    _go(root, "test_a.py\tk2\n", capsys=capsys)
    assert _runs(root) == 2


def test_a_suite_with_no_key_always_runs(project: Callable[..., Path], capsys: pytest.CaptureFixture[str]) -> None:
    root = project(a=COUNT)
    _go(root, "test_a.py\t\n", capsys=capsys)
    _go(root, "test_a.py\n", capsys=capsys)
    assert _runs(root) == 2


def test_a_red_run_exits_1_and_records_nothing(project: Callable[..., Path], capsys: pytest.CaptureFixture[str]) -> None:
    root = project(a=FAIL)
    assert _go(root, "test_a.py\tk1\n", capsys=capsys)[0] == 1
    assert not (root / "receipts.json").exists()
    assert _go(root, "test_a.py\tk1\n", capsys=capsys)[0] == 1  # still not skipped


def test_nothing_to_run_is_a_pass_that_starts_no_pytest(project: Callable[..., Path], capsys: pytest.CaptureFixture[str]) -> None:
    root = project(a=COUNT)
    code, _out, err = _go(root, "", capsys=capsys)
    assert (code, _runs(root)) == (0, 0)
    assert "nothing to run" in err


def test_the_arguments_after_the_double_dash_reach_pytest(project: Callable[..., Path], capsys: pytest.CaptureFixture[str]) -> None:
    root = project(a=PASS + FAIL)
    assert _go(root, "test_a.py\t\n", "--", "-k", "ok", capsys=capsys)[0] == 0


def test_a_run_waits_for_a_free_slot_and_says_who_holds_it(project: Callable[..., Path], capsys: pytest.CaptureFixture[str]) -> None:
    root = project(a=PASS)
    leases = Leases(root / "leases")
    held = leases.acquire("tests", 1, label="another gate")
    threading.Timer(1.0, held.release).start()
    began = time.monotonic()
    code, _out, err = _go(root, "test_a.py\t\n", capsys=capsys)
    assert code == 0
    assert time.monotonic() - began >= 0.9
    assert "waiting for a test slot" in err
    assert "another gate" in err


def test_a_malformed_plan_line_is_a_usage_error(project: Callable[..., Path], capsys: pytest.CaptureFixture[str]) -> None:
    root = project(a=PASS)
    code, _out, err = _go(root, "a\tb\tc\n", capsys=capsys)
    assert code == 2
    assert "plan line" in err
