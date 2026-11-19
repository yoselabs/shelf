from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from any_speech import EngineMissingError, default_transcriber
from any_speech.defaults import find_fluidaudio
from any_speech.setup import FLUIDAUDIO_COMMIT, SetupError, install_fluidaudio, installed_binary


def _binary(path: Path, body: bytes = b"#!/bin/sh\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    path.chmod(0o755)
    return path


def test_locate_prefers_the_environment_then_the_installed_copy_then_path_then_local_bin(tmp_path: Path) -> None:
    env_bin = _binary(tmp_path / "e" / "fluidaudiocli")
    installed = _binary(installed_binary({}, tmp_path))
    on_path = _binary(tmp_path / "p" / "fluidaudiocli")
    local = _binary(tmp_path / ".local" / "bin" / "fluidaudiocli")
    env = {"ANY_SPEECH_FLUIDAUDIO_BIN": str(env_bin), "PATH": str(on_path.parent)}
    assert find_fluidaudio(env, tmp_path) == env_bin
    assert find_fluidaudio({"PATH": str(on_path.parent)}, tmp_path) == installed
    installed.unlink()
    assert find_fluidaudio({"PATH": str(on_path.parent)}, tmp_path) == on_path
    on_path.unlink()
    assert find_fluidaudio({"PATH": ""}, tmp_path) == local


def test_a_missing_binary_names_the_setup_command(tmp_path: Path) -> None:
    with pytest.raises(EngineMissingError, match="any-speech setup fluidaudio"):
        find_fluidaudio({"PATH": ""}, tmp_path)


def test_runtime_is_the_pinned_commit_and_the_binary_hash_for_an_installed_build(tmp_path: Path) -> None:
    binary = _binary(installed_binary({}, tmp_path), b"build-one")
    binary.with_name("fluidaudiocli.commit").write_text(FLUIDAUDIO_COMMIT, encoding="utf-8")
    runtime = default_transcriber(env={"PATH": ""}, home=tmp_path).identity.runtime
    assert runtime.startswith(f"fluidaudio-{FLUIDAUDIO_COMMIT[:8]}+")
    other = default_transcriber(
        env={"ANY_SPEECH_FLUIDAUDIO_BIN": str(_binary(tmp_path / "x" / "fluidaudiocli", b"another"))}, home=tmp_path
    )
    assert other.identity.runtime.startswith("fluidaudio-unknown+")
    assert other.identity.runtime != runtime


def _toolchain(tmp_path: Path, *names: str) -> dict[str, str]:
    for name in names:
        _binary(tmp_path / "tools" / name)
    return {"PATH": str(tmp_path / "tools")}


def test_setup_clones_at_the_pin_builds_and_installs(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def run(args: Any, *, cwd: Path | None = None) -> None:
        argv = [Path(str(args[0])).name, *(str(a) for a in args[1:])]
        calls.append(argv)
        if argv[:2] == ["git", "clone"]:
            (tmp_path / "work").mkdir(exist_ok=True)
        if argv[:2] == ["swift", "build"]:
            _binary(tmp_path / "work" / ".build" / "release" / "fluidaudiocli", b"built")

    target = install_fluidaudio(_toolchain(tmp_path, "git", "swift"), tmp_path, run=run, work=tmp_path / "work")
    assert target.read_bytes() == b"built"
    assert target.with_name("fluidaudiocli.commit").read_text(encoding="utf-8") == FLUIDAUDIO_COMMIT
    assert any(c[:2] == ["git", "checkout"] and c[-1] == FLUIDAUDIO_COMMIT for c in calls)
    assert any("--product" in c and "fluidaudiocli" in c for c in calls)


def test_setup_says_when_swift_is_missing(tmp_path: Path) -> None:
    with pytest.raises(SetupError, match="Xcode"):
        install_fluidaudio({"PATH": ""}, tmp_path, run=lambda *_a, **_k: None, work=tmp_path / "w")


def test_a_failing_build_is_an_error_not_a_half_install(tmp_path: Path) -> None:
    def run(args: Any, *, cwd: Path | None = None) -> None:
        raise subprocess.CalledProcessError(1, args)

    with pytest.raises(SetupError, match="failed"):
        install_fluidaudio(_toolchain(tmp_path, "git", "swift"), tmp_path, run=run, work=tmp_path / "w")
    assert not installed_binary({}, tmp_path).exists()


def test_a_setup_step_that_exits_nonzero_or_runs_out_of_time_is_a_failed_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from any_speech import setup  # noqa: PLC0415

    with pytest.raises(subprocess.CalledProcessError) as bad:
        setup._run(["sh", "-c", "exit 3"])
    assert bad.value.returncode == 3
    monkeypatch.setattr(setup, "_STEP_TIMEOUT", 0.3)
    with pytest.raises(subprocess.CalledProcessError) as slow:
        setup._run(["sleep", "30"], cwd=tmp_path)
    assert slow.value.returncode == 124
