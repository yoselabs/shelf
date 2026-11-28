"""`python -m any_gate test`: plan lines in, units with a receipt skipped, the rest run by a runner under a lease, receipts on green."""

from __future__ import annotations

import io
import os
import sys
import textwrap
import threading
import time
from typing import TYPE_CHECKING

import pytest
from any_gate.cli import main
from any_gate.receipts import Receipts
from any_gate.state import GateState
from any_lease import Leases

if TYPE_CHECKING:
    from pathlib import Path

# A runner is any command that takes the units last and exits 0 when they are green. This one logs the units it was given; a unit named
# `bad...` fails, one named `hang...` goes silent, one named `chatty...` prints.
RUNNER = textwrap.dedent(
    """
    import sys, time
    units = sys.argv[1:]
    open("ran.log", "a").write(" ".join(units) + "\\n")
    if any(u.startswith("hang") for u in units):
        time.sleep(30)
    for u in units:
        if u.startswith("chatty"):
            print("output from the runner")
    sys.exit(1 if any(u.startswith("bad") for u in units) else 0)
    """
)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "runner.py").write_text(RUNNER)
    return tmp_path


def _go(root: Path, plan: str, *args: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = main(
        [
            "test",
            "--receipts",
            str(root / "receipts.json"),
            "--lease-root",
            str(root / "leases"),
            "--cwd",
            str(root),
            *args,
            "--",
            sys.executable,
            "runner.py",
        ],
        stdin=io.StringIO(plan),
    )
    out = capsys.readouterr()
    return code, out.out, out.err


def _ran(root: Path) -> list[str]:
    log = root / "ran.log"
    return log.read_text().splitlines() if log.exists() else []


def test_a_unit_runs_and_its_green_result_is_not_run_again_under_the_same_key(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _go(root, "a\tk1\n", capsys=capsys)[0] == 0
    assert _ran(root) == ["a"]
    code, _out, err = _go(root, "a\tk1\n", capsys=capsys)
    assert (code, _ran(root)) == (0, ["a"])
    assert "1 suite(s) skipped" in err


def test_a_changed_key_runs_the_unit_again(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _go(root, "a\tk1\n", capsys=capsys)
    _go(root, "a\tk2\n", capsys=capsys)
    assert _ran(root) == ["a", "a"]


def test_a_unit_with_no_key_always_runs(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _go(root, "a\t\n", capsys=capsys)
    _go(root, "a\n", capsys=capsys)
    assert _ran(root) == ["a", "a"]


def test_the_units_left_reach_the_runner_together_and_in_plan_order(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _go(root, "b\tk\n", capsys=capsys)
    _go(root, "a\tk\nb\tk\nc\tk\n", capsys=capsys)
    assert _ran(root) == ["b", "a c"]


def test_a_red_run_exits_1_and_records_nothing(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _go(root, "bad\tk1\n", capsys=capsys)[0] == 1
    assert not (root / "receipts.json").exists()
    assert _go(root, "bad\tk1\n", capsys=capsys)[0] == 1  # still not skipped


def test_nothing_to_run_is_a_pass_that_starts_no_runner(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _out, err = _go(root, "", capsys=capsys)
    assert (code, _ran(root)) == (0, [])
    assert "nothing to run" in err


def test_the_runners_output_reaches_the_caller(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert "output from the runner" in _go(root, "chatty\t\n", capsys=capsys)[1]


def test_a_runner_that_outlives_the_wall_limit_is_stopped_and_named(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _out, err = _go(root, "hang\tk\n", "--wall", "1", capsys=capsys)
    assert code == 1
    assert "wall limit" in err
    assert not (root / "receipts.json").exists()


def test_a_runner_that_goes_silent_is_stopped_by_the_idle_limit(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _out, err = _go(root, "hang\tk\n", "--idle", "1", capsys=capsys)
    assert code == 1
    assert "idle limit" in err


def test_no_runner_is_a_usage_error(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["test", "--receipts", str(root / "r.json"), "--cwd", str(root)], stdin=io.StringIO("a\tk\n"))
    assert code == 2
    assert "give the runner" in capsys.readouterr().err


def test_a_run_waits_for_a_free_slot_and_says_who_holds_it(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    held = Leases(root / "leases").acquire("tests", 1, label="another gate")
    threading.Timer(1.0, held.release).start()
    began = time.monotonic()
    code, _out, err = _go(root, "a\t\n", capsys=capsys)
    assert code == 0
    assert time.monotonic() - began >= 0.9
    assert "waiting for a test slot" in err
    assert "another gate" in err


def test_a_gate_that_waited_for_the_slot_skips_what_the_holder_passed_meanwhile(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    receipts = Receipts(root / "receipts.json")
    held = Leases(root / "leases").acquire("tests", 1, label="another gate")

    def finish() -> None:  # the holder's run ends green: it records `a` and lets the slot go
        receipts.record("a", "k1")
        held.release()

    threading.Timer(1.0, finish).start()
    code, _out, err = _go(root, "a\tk1\nb\tk2\n", capsys=capsys)
    assert code == 0
    assert _ran(root) == ["b"]  # `a` passed while this gate queued: it is not run again
    assert "skipped, unchanged since they passed" in err


def test_a_malformed_plan_line_is_a_usage_error(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _out, err = _go(root, "a\tb\tc\n", capsys=capsys)
    assert code == 2
    assert "plan line" in err


def test_a_run_ends_with_one_line_saying_what_ran_what_was_skipped_and_how_long(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _go(root, "a\tk1\n", capsys=capsys)
    _code, _out, err = _go(root, "a\tk1\nb\tk2\n", capsys=capsys)
    assert any(
        line.startswith("any-gate: test: ran 1 of 2 suite(s)") and "1 unchanged" in line and line.endswith("s") for line in err.splitlines()
    )


def test_a_test_step_with_an_empty_plan_marks_the_gate_unjudged_so_no_pass_is_recorded(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The incident: the gate said run, the plan held 0 suites, and the tree was recorded green."""
    import subprocess  # noqa: PLC0415

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(repo)]
    (repo / "a.py").write_text("x = 1\n")
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "c"], check=True)
    receipts = str(tmp_path / "receipts.json")
    assert main(["start", "--repo", str(repo), "--receipts", receipts]) == 0
    assert (
        main(["test", "--receipts", receipts, "--lease-root", str(tmp_path / "l"), "--cwd", str(repo), "--", "true"], stdin=io.StringIO(""))
        == 0
    )
    assert main(["passed", "--repo", str(repo), "--receipts", receipts]) == 0
    assert "judged nothing" in capsys.readouterr().err
    assert not GateState(repo, Receipts(tmp_path / "receipts.json"), dict(os.environ)).green("check")  # the push still runs the gate


def test_the_steps_command_takes_the_gate_lease_before_it_decides_what_to_skip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import contextmanager  # noqa: PLC0415

    from any_gate import cli  # noqa: PLC0415

    order: list[str] = []

    @contextmanager
    def fake_hold(*_a: object, **_k: object):
        order.append("lease")
        yield dict(__import__("os").environ)

    def fake_decide(*_a: object, **_k: object) -> tuple[dict[str, str], dict[str, str]]:
        order.append("decide")
        return {}, {}

    monkeypatch.setattr(cli, "hold", fake_hold)
    monkeypatch.setattr(cli, "_decide", fake_decide)
    monkeypatch.setattr(cli, "run_and_report", lambda *_a, **_k: 0)
    assert main(["steps", "--repo", str(tmp_path), "--lease-root", str(tmp_path / "l"), "one"]) == 0
    assert order == ["lease", "decide"]
