"""A per-user macOS LaunchAgent: render, load, unload, and report it.

A ``~/Library/LaunchAgents/<label>.plist`` with ``RunAtLoad`` and ``KeepAlive`` starts a
program at login and lets launchd relaunch it when it dies. This module writes that plist
and loads it into the user's GUI domain (``launchctl bootstrap gui/<uid>``).

Every launchd effect goes through an injected ``run_launchctl`` runner, so the logic is
testable against a temporary LaunchAgents folder without touching the real launchd.

Two things launchd does not tell you up front:

- **A refused bootstrap leaves the plist behind.** ``launchctl bootstrap`` fails when the
  label is already loaded or the domain rejects it. A plist on disk with nothing loaded
  reads as installed forever, so :func:`install` removes its own write and raises
  :class:`LaunchdError`.
- **launchd's PATH is four system folders.** Homebrew's ``/opt/homebrew/bin`` and
  ``~/.local/bin`` are not on it, so a program that shells out to a tool installed there
  finds nothing at login. :func:`launch_path` puts the folders holding the named tools in
  front.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

#: The PATH launchd starts an agent with, and nothing else.
LAUNCHD_PATH = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")


class LaunchdError(RuntimeError):
    """launchd refused an operation the agent depends on."""


class LaunchctlResult(Protocol):
    returncode: int


class Launchctl(Protocol):
    def __call__(self, cmd: list[str]) -> LaunchctlResult: ...


@dataclass(frozen=True)
class LoginItemStatus:
    """Whether the agent's plist is on disk and whether launchd has it loaded."""

    label: str
    plist_path: Path
    installed: bool  # the plist file exists
    loaded: bool  # launchd knows the label (RunAtLoad will fire it at login)


def run_launchctl(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """The real runner: ``cmd`` as a subprocess, output captured, never raising on exit code."""
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def user_agents_dir() -> Path:
    """``~/Library/LaunchAgents``: where a per-user agent's plist lives."""
    return Path.home() / "Library" / "LaunchAgents"


def domain() -> str:
    """The current user's GUI launchd domain, ``gui/<uid>``."""
    return f"gui/{os.getuid()}"


def plist_path(label: str, agents_dir: Path) -> Path:
    return agents_dir / f"{label}.plist"


def launch_path(tools: Sequence[str], which: Callable[[str], str | None] = shutil.which) -> str:
    """launchd's PATH with the folders holding ``tools`` in front, each folder once.

    A tool ``which`` cannot find, or one already in a launchd folder, adds nothing.
    """
    folders: list[str] = []
    for tool in tools:
        found = which(tool)
        if found is None:
            continue
        folder = str(Path(found).parent)
        if folder not in folders and folder not in LAUNCHD_PATH:
            folders.append(folder)
    return ":".join([*folders, *LAUNCHD_PATH])


def render_plist(
    *,
    label: str,
    argv: Sequence[str],
    env: Mapping[str, str],
    log_path: Path,
    working_dir: Path | None = None,
    run_at_load: bool = True,
    keep_alive: bool = True,
    process_type: str = "Interactive",
) -> str:
    """The LaunchAgent plist as a string — no filesystem or launchd effects.

    stdout and stderr both go to ``log_path``. ``process_type`` defaults to
    ``Interactive``, launchd's class for an agent the user sees (a menu-bar app).
    """
    doc: dict[str, object] = {
        "Label": label,
        "ProgramArguments": list(argv),
    }
    if working_dir is not None:
        doc["WorkingDirectory"] = str(working_dir)
    doc |= {
        "EnvironmentVariables": dict(env),
        "RunAtLoad": run_at_load,
        "KeepAlive": keep_alive,
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(log_path),
        "ProcessType": process_type,
    }
    return plistlib.dumps(doc).decode()


def install(
    *,
    label: str,
    argv: Sequence[str],
    env: Mapping[str, str],
    log_path: Path,
    agents_dir: Path,
    working_dir: Path | None = None,
    run_launchctl: Launchctl = run_launchctl,
) -> Path:
    """Write the agent's plist and load it into launchd; return the plist path.

    Raises :class:`LaunchdError` when ``launchctl bootstrap`` refuses, after removing the
    plist it wrote: a file on disk with nothing loaded would report installed forever.
    """
    doc = render_plist(label=label, argv=argv, env=env, log_path=log_path, working_dir=working_dir)
    agents_dir.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    path = plist_path(label, agents_dir)
    path.write_text(doc, encoding="utf-8")
    result = run_launchctl(["launchctl", "bootstrap", domain(), str(path)])
    if result.returncode != 0:
        path.unlink(missing_ok=True)
        msg = f"launchctl bootstrap refused {label} (exit {result.returncode})"
        raise LaunchdError(msg)
    return path


def uninstall(label: str, *, agents_dir: Path, run_launchctl: Launchctl = run_launchctl) -> bool:
    """Unload the agent and remove its plist; return whether anything was removed."""
    path = plist_path(label, agents_dir)
    if not path.exists():
        return False
    run_launchctl(["launchctl", "bootout", f"{domain()}/{label}"])
    path.unlink(missing_ok=True)
    return True


def status(label: str, *, agents_dir: Path, run_launchctl: Launchctl = run_launchctl) -> LoginItemStatus:
    """Whether the plist is on disk and whether launchd currently has the label loaded."""
    path = plist_path(label, agents_dir)
    loaded = run_launchctl(["launchctl", "print", f"{domain()}/{label}"]).returncode == 0
    return LoginItemStatus(label=label, plist_path=path, installed=path.exists(), loaded=loaded)


__all__ = [
    "LAUNCHD_PATH",
    "Launchctl",
    "LaunchctlResult",
    "LaunchdError",
    "LoginItemStatus",
    "domain",
    "install",
    "launch_path",
    "plist_path",
    "render_plist",
    "run_launchctl",
    "status",
    "uninstall",
    "user_agents_dir",
]
