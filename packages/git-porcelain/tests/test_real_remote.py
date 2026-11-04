"""Fetch retries only ref races, with one process per attempt and bounded waiting."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from git_porcelain import GitUnavailable, RealRepo, RefRace

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("operation", ["fetch", "sync"])
@pytest.mark.parametrize("failures", [1, 4, 5])
def test_fetch_retries_ref_races_with_a_five_attempt_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str, failures: int
) -> None:
    calls: list[list[str]] = []
    rests: list[float] = []

    def process(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        calls.append(args)
        err = b"error: cannot lock ref 'refs/remotes/origin/main': is at abc but expected def\n" if len(calls) <= failures else b""
        return subprocess.CompletedProcess(args, int(bool(err)), b"", err)

    monkeypatch.setattr(subprocess, "run", process)
    repo = RealRepo(tmp_path, sleep=rests.append)
    if operation == "fetch" and failures == 5:
        with pytest.raises(RefRace):
            repo.fetch()
    else:
        result = repo.fetch() if operation == "fetch" else repo.sync()
        assert type(result).__name__ == ("Offline" if failures == 5 else "CommandResult" if operation == "fetch" else "Synced")
    assert len(calls) == min(failures + 1, 5)
    assert rests == [0.1 * (attempt + 1) for attempt in range(min(failures, 4))]
    assert all("fetch" in args for args in calls)


@pytest.mark.parametrize("operation", ["fetch", "sync"])
@pytest.mark.parametrize("error", [b"fatal: remote end hung up\n", b"fatal: index.lock exists\n", b"error: unknown refusal\n"])
def test_fetch_does_not_retry_other_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str, error: bytes) -> None:
    calls: list[list[str]] = []
    rests: list[float] = []

    def process(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 128, b"", error)

    monkeypatch.setattr(subprocess, "run", process)
    repo = RealRepo(tmp_path, sleep=rests.append)
    if operation == "fetch":
        with pytest.raises(GitUnavailable):
            repo.fetch()
    else:
        assert type(repo.sync()).__name__ == "Offline"
    assert len(calls) == 1
    assert rests == []
