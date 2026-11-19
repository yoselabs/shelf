"""Where the bd binary comes from, and bd's own wire strings for status and dependency type."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from child_env import NotFound

from beads_client import DEP_BLOCKS, Bd, BeadStatus
from beads_client.testing import Script

if TYPE_CHECKING:
    from pathlib import Path


def test_bd_is_found_on_the_injected_path(tmp_path: Path) -> None:
    exe = tmp_path / "bd"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    assert Bd("t", env={"PATH": str(tmp_path)}, run=Script()).exe == str(exe)


def test_no_bd_on_the_path_raises_not_a_bare_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ambient = tmp_path / "ambient"
    ambient.mkdir()
    (ambient / "bd").write_text("#!/bin/sh\n")
    (ambient / "bd").chmod(0o755)
    monkeypatch.setenv("PATH", f"{ambient}{os.pathsep}{os.environ.get('PATH', '')}")
    with pytest.raises(NotFound):
        Bd("t", env={"PATH": str(tmp_path / "empty")}, run=Script())
    with pytest.raises(NotFound):
        Bd("t", run=Script())  # no env, no exe: the process PATH is not consulted


def test_an_explicit_exe_needs_no_search() -> None:
    assert Bd("t", exe="/opt/bd", run=Script()).exe == "/opt/bd"


def test_status_values_are_bds_wire_strings() -> None:
    assert [s.value for s in BeadStatus] == ["open", "in_progress", "blocked", "deferred", "closed"]
    assert BeadStatus.IN_PROGRESS == "in_progress"  # a str: it compares with Bead.status and goes into argv as is


def test_the_blocks_dependency_type_is_bds_default_name() -> None:
    assert DEP_BLOCKS == "blocks"


def test_a_status_member_goes_to_bd_as_its_wire_string(bd: Bd, script: Script) -> None:
    script.say("[]")
    bd.find(BeadStatus.DEFERRED)
    assert script.calls[-1][script.calls[-1].index("--status") + 1] == "deferred"
