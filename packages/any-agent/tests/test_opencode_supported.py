"""The command sandbox is asked for as a tool (`sandbox-exec`), never as an operating system."""

from __future__ import annotations

from typing import TYPE_CHECKING

from child_env import NotFound

from any_agent.harnesses.opencode import OpenCodeHarness

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_supported_when_sandbox_exec_is_on_the_injected_path(tmp_path: Path) -> None:
    fake = tmp_path / "sandbox-exec"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    assert OpenCodeHarness(env={"PATH": str(tmp_path)}).supported() is True


def test_unsupported_when_sandbox_exec_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(name: str, *_args: object) -> object:
        raise NotFound(name, ())

    monkeypatch.setattr("any_agent.harnesses.opencode.find", missing)
    assert OpenCodeHarness(env={}).supported() is False
