"""A red run prints the failing ids and totals, not hundreds of KB of tracebacks; the full stream stays in a log."""

from __future__ import annotations

from typing import TYPE_CHECKING

from any_gate_python.compact import Compact

if TYPE_CHECKING:
    from pathlib import Path


def _stream(failures: int) -> list[str]:
    lines = ["....F.. [ 50%]\n", "=" * 20 + " FAILURES " + "=" * 20 + "\n"]
    for n in range(failures):
        lines += [f"___ test_{n} ___\n", f"    def test_{n}():\n", "E   AssertionError: boom\n"] + ["    traceback line\n"] * 40
    lines += ["=" * 10 + " warnings summary " + "=" * 10 + "\n", "  a warning\n" * 3]
    lines += ["=" * 10 + " short test summary info " + "=" * 10 + "\n"]
    lines += [f"FAILED tests/test_x.py::test_{n} - AssertionError: boom\n" for n in range(failures)]
    lines += [f"{failures} failed, 10 passed in 1.00s\n"]
    return lines


def _run(tmp_path: Path, failures: int) -> tuple[str, str, Path]:
    out: list[str] = []
    compact = Compact(out.append, tmp_path / "last.log")
    stream = _stream(failures)
    for line in stream:
        compact.feed(line)
    compact.finish()
    return "".join(out), "".join(stream), compact.log_path


def test_many_failures_print_ids_totals_and_the_log_path(tmp_path: Path) -> None:
    shown, full, log = _run(tmp_path, 57)
    assert shown.count("FAILED tests/test_x.py::") == 57
    assert "57 failed, 10 passed" in shown
    assert str(log) in shown
    assert "traceback line" not in shown
    assert len(shown) < len(full) / 10
    assert log.read_text(encoding="utf-8") == full


def test_a_few_failures_keep_their_tracebacks(tmp_path: Path) -> None:
    shown, _, _ = _run(tmp_path, 2)
    assert "AssertionError: boom" in shown
    assert "traceback line" in shown
    assert shown.count("FAILED tests/test_x.py::") == 2


def test_a_green_run_prints_everything_it_got(tmp_path: Path) -> None:
    out: list[str] = []
    compact = Compact(out.append, tmp_path / "last.log")
    for line in ("....... [100%]\n", "7 passed in 0.10s\n"):
        compact.feed(line)
    compact.finish()
    assert "".join(out) == "....... [100%]\n7 passed in 0.10s\n"
