"""Captured diagnostics replace invalid bytes and hide URL credentials without losing raw data."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from git_porcelain import GitTimeout, GitUnavailable, RealRepo
from git_porcelain.errors import GitError
from git_porcelain.porcelain import run_git_result
from git_porcelain.real_done import Done, unavailable

if TYPE_CHECKING:
    from pathlib import Path


def test_done_keeps_raw_bytes_but_replaces_invalid_utf8_in_diagnostics() -> None:
    done = Done(128, b"stdout-\xff\n", "stderr-\ufffd\n")
    assert done.raw == b"stdout-\xff\n"
    assert done.out == "stdout-\ufffd\n"
    assert done.output == "stdout-\ufffd\nstderr-\ufffd"
    assert done.tail == "stderr-\ufffd"
    error = unavailable(("fetch",), done)
    assert error.output == done.output
    assert "stderr-\ufffd" in str(error)


@pytest.mark.parametrize("outcome", ["success", "refusal", "timeout"])
def test_runner_diagnostics_replace_invalid_utf8(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str) -> None:
    def process(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(args, 1, output=b"out-\xff\n", stderr=b"err-\xfe\n")
        return subprocess.CompletedProcess(args, int(outcome == "refusal"), b"out-\xff\n", b"err-\xfe\n")

    monkeypatch.setattr(subprocess, "run", process)
    repo = RealRepo(tmp_path)
    if outcome == "success":
        done = repo.run(tmp_path, "fetch", pin=False)
        assert done.out == "out-\ufffd\n"
        assert done.err == "err-\ufffd\n"
        assert done.output == "out-\ufffd\nerr-\ufffd"
    else:
        with pytest.raises(GitTimeout if outcome == "timeout" else GitUnavailable) as caught:
            repo.run(tmp_path, "fetch", pin=False)
        assert caught.value.output == "out-\ufffd\nerr-\ufffd"
        assert not any(0xD800 <= ord(char) <= 0xDFFF for char in str(caught.value))


@pytest.mark.parametrize("outcome", ["success", "refusal", "timeout"])
@pytest.mark.parametrize("path_api", [False, True])
def test_runner_redacts_credentials_in_both_output_streams(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str, *, path_api: bool
) -> None:
    stdout = b"To https://user:pass@example.invalid/repo\n"
    stderr = b"fatal: ssh://user@example.invalid/repo\n"
    expected = "To https://***@example.invalid/repo\nfatal: ssh://***@example.invalid/repo"

    def process(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes] | subprocess.CompletedProcess[str]:
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(args, 1, output=stdout, stderr=stderr)
        if path_api:
            return subprocess.CompletedProcess(args, int(outcome == "refusal"), stdout.decode(), stderr.decode())
        return subprocess.CompletedProcess(args, int(outcome == "refusal"), stdout, stderr)

    monkeypatch.setattr(subprocess, "run", process)
    repo = RealRepo(tmp_path)
    if outcome == "success":
        if path_api:
            assert run_git_result(tmp_path, "fetch").output == expected
        else:
            done = repo.run(tmp_path, "fetch", pin=False)
            assert done.output == expected
            assert "user" not in done.tail
            assert done.raw == stdout
            assert done.out == stdout.decode()
    else:
        with pytest.raises(GitError) as caught:
            if path_api:
                run_git_result(tmp_path, "fetch")
            else:
                repo.run(tmp_path, "fetch", pin=False)
        assert caught.value.output == expected
        assert "user" not in str(caught.value)
        if isinstance(caught.value, GitUnavailable):
            assert "user" not in caught.value.tail
