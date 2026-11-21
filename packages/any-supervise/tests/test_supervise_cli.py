"""The console script: --help answers and changes nothing, an unknown flag exits 2, a library failure is exit 2 and a message."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import any_supervise.__main__ as cli
from any_supervise import BusyError, StartFailedError

if TYPE_CHECKING:
    from collections.abc import Callable


def script(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(Path(sys.executable).parent / "any-supervise"), *args], cwd=cwd, capture_output=True, text=True, check=False, timeout=60
    )


@pytest.mark.parametrize("verb", [None, "up", "status", "roll", "down", "logs"])
def test_help_answers_and_changes_nothing(tmp_path: Path, verb: str | None) -> None:
    done = script(*([verb] if verb else []), "--help", cwd=tmp_path)
    assert done.returncode == 0
    assert "usage: any-supervise" in done.stdout
    assert list(tmp_path.iterdir()) == []


def test_an_unknown_flag_exits_2(tmp_path: Path) -> None:
    assert script("status", "--no-such-flag", cwd=tmp_path).returncode == 2


@pytest.mark.parametrize(
    "failure",
    [
        lambda: ExceptionGroup("two stops failed", [RuntimeError("a"), RuntimeError("b")]),
        lambda: BusyError("busy"),
        lambda: StartFailedError("no start time"),
    ],
)
def test_a_library_failure_is_exit_2_and_a_message_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], failure: Callable[[], BaseException]
) -> None:
    spec = tmp_path / "fleet.toml"
    spec.write_text(
        'state = "st"\nversion_cmd = ["true"]\nversion_cwd = "."\n[[worker]]\nname = "w"\ncommand = ["true"]\nlog = "l"\n', encoding="utf-8"
    )

    def boom(*_a: object) -> object:
        raise failure()

    monkeypatch.setattr(cli, "down", boom)
    assert cli.main(["down", str(spec)]) == 2
    assert "any-supervise:" in capsys.readouterr().err
