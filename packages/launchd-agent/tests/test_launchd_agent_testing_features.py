"""launchd_agent.testing, stated as Gherkin."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import launchd_agent as la
import pytest
from launchd_agent.testing import FakeLaunchctl, RefusingLaunchctl, refusing_launchctl_bin
from pytest_bdd import given, parsers, scenarios, then, when

if TYPE_CHECKING:
    from pathlib import Path

scenarios("features/launchctl_doubles.feature")


@dataclass
class World:
    root: Path
    ctl: FakeLaunchctl = field(default_factory=FakeLaunchctl)
    statuses: list[la.LoginItemStatus] = field(default_factory=list)
    failure: Exception | None = None
    ran: Any = None

    @property
    def agents(self) -> Path:
        return self.root / "LaunchAgents"


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(root=tmp_path)


def _install(world: World, label: str) -> None:
    la.install(label=label, argv=["/bin/true"], env={}, log_path=world.root / "agent.log", agents_dir=world.agents, run_launchctl=world.ctl)


@given("a fake launchctl")
def _fake(world: World) -> None:
    world.ctl = FakeLaunchctl()


@given("a fake launchctl that refuses bootstrap")
def _refusing(world: World) -> None:
    world.ctl = RefusingLaunchctl()


@given("a folder with the refusing launchctl first on the path")
def _on_path(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = refusing_launchctl_bin(world.root / "bin")
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")


@when(parsers.parse('an agent "{label}" is installed, checked and uninstalled'))
def _round_trip(world: World, label: str) -> None:
    _install(world, label)
    world.statuses.append(la.status(label, agents_dir=world.agents, run_launchctl=world.ctl))
    la.uninstall(label, agents_dir=world.agents, run_launchctl=world.ctl)
    world.statuses.append(la.status(label, agents_dir=world.agents, run_launchctl=world.ctl))


@when(parsers.parse('an agent "{label}" is installed'))
def _installed(world: World, label: str) -> None:
    try:
        _install(world, label)
    except la.LaunchdError as exc:
        world.failure = exc


@when(parsers.parse('"{command}" runs by name'))
def _runs(world: World, command: str) -> None:
    world.ran = subprocess.run(command.split(), capture_output=True, text=True, check=False)


@then("the status after install is installed and loaded")
def _after_install(world: World) -> None:
    assert world.statuses[0].installed
    assert world.statuses[0].loaded


@then("the status after uninstall is neither")
def _after_uninstall(world: World) -> None:
    assert not world.statuses[1].installed
    assert not world.statuses[1].loaded


@then(parsers.parse('the fake saw "{subs}"'))
def _saw(world: World, subs: str) -> None:
    assert [c[1] for c in world.ctl.calls] == subs.split(", ")


@then(parsers.parse('the install fails naming "{text}"'))
def _install_fails(world: World, text: str) -> None:
    assert world.failure is not None
    assert text in str(world.failure)


@then("no plist is left behind")
def _no_plist(world: World) -> None:
    assert not list(world.agents.glob("*.plist"))


@then(parsers.parse('it exits {code:d} saying "{text}"'))
def _exits(world: World, code: int, text: str) -> None:
    assert world.ran.returncode == code
    assert text in world.ran.stderr
