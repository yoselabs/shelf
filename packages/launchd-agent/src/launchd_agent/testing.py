"""Test doubles for ``launchctl``: nothing a test runs reaches the user's launchd.

- :class:`FakeLaunchctl` is a ``run_launchctl`` that records each command and keeps the set of
  loaded labels, so install, status and uninstall round-trip.
- :class:`RefusingLaunchctl` refuses every ``bootstrap`` the way launchd does (exit 5).
- :func:`refusing_launchctl_bin` writes a ``launchctl`` program that refuses everything, for a
  folder put first on ``PATH``: code that shells out by name hits it instead of launchd.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, override

__all__ = ["REFUSED", "FakeLaunchctl", "LaunchctlCall", "RefusingLaunchctl", "refusing_launchctl_bin"]

#: What the refusing program prints to stderr.
REFUSED: Final = "launchctl is not available to tests"


@dataclass
class LaunchctlCall:
    """One fake run: a :class:`launchd_agent.LaunchctlResult`."""

    returncode: int
    stdout: str = ""
    stderr: str = ""


class FakeLaunchctl:
    """Records launchctl invocations and tracks which labels are loaded."""

    def __init__(self) -> None:
        self.loaded: set[str] = set()
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str]) -> LaunchctlCall:
        self.calls.append(cmd)
        sub = cmd[1]
        if sub == "bootstrap":  # launchctl bootstrap gui/<uid> <plist>
            self.loaded.add(Path(cmd[3]).stem)
        elif sub == "bootout":  # launchctl bootout gui/<uid>/<label>
            self.loaded.discard(cmd[2].rsplit("/", 1)[-1])
        elif sub == "print":  # launchctl print gui/<uid>/<label>
            return LaunchctlCall(0 if cmd[2].rsplit("/", 1)[-1] in self.loaded else 1)
        return LaunchctlCall(0)


class RefusingLaunchctl(FakeLaunchctl):
    """``launchctl bootstrap`` refuses: the label is already loaded, or the domain rejects it."""

    @override
    def __call__(self, cmd: list[str]) -> LaunchctlCall:
        if cmd[1] == "bootstrap":
            self.calls.append(cmd)
            return LaunchctlCall(5, stderr="Bootstrap failed: 5: Input/output error")
        return super().__call__(cmd)


def refusing_launchctl_bin(folder: Path) -> Path:
    """Write ``folder/launchctl``, a program that refuses every command (exit 1); return ``folder``."""
    folder.mkdir(parents=True, exist_ok=True)
    fake = folder / "launchctl"
    fake.write_text(f'#!/bin/sh\necho "{REFUSED}" >&2\nexit 1\n', encoding="utf-8")
    fake.chmod(0o755)
    return folder
