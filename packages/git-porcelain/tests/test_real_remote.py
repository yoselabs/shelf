"""Fetch retries only ref races, with one process per attempt and bounded waiting."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from git_porcelain import GitReadFailure, GitUnavailable, RealRepo, RefRace
from git_porcelain.testing import FakeRemote, FakeRepo, apply_hermetic_env, git

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


@pytest.mark.parametrize(
    ("rc", "stdout", "stderr"), [(128, b"", b"fatal: cannot read config\n"), (0, b"", b""), (1, b"partial", b"read failed")]
)
def test_identity_does_not_turn_origin_read_failure_into_absence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rc: int, stdout: bytes, stderr: bytes
) -> None:
    """shelf-7qsd: an observer must distinguish unknown origin from a missing origin."""

    def process(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        if "rev-parse" in args:
            return subprocess.CompletedProcess(args, 0, str(tmp_path / ".git").encode(), b"")
        return subprocess.CompletedProcess(args, rc, stdout, stderr)

    monkeypatch.setattr(subprocess, "run", process)
    with pytest.raises(GitReadFailure):
        RealRepo(tmp_path, memoize=False).identity()


@pytest.mark.parametrize("implementation", ["real", "fake"])
def test_origin_changes_do_not_change_local_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, implementation: str) -> None:
    """shelf-7qsd: origin is optional display metadata, independent of local identity."""
    apply_hermetic_env(monkeypatch, home=tmp_path / "home")
    if implementation == "real":
        git(tmp_path, "init", "-q", "-b", "main")
        repo = RealRepo(tmp_path, memoize=False)
    else:
        repo = FakeRepo.init(tmp_path)
    before = repo.identity()
    assert before.origin_url is None
    if isinstance(repo, FakeRepo):
        repo.add_remote("origin", FakeRemote("https://example.invalid/first"))
    else:
        git(tmp_path, "remote", "add", "origin", "https://example.invalid/first")
    first = repo.identity()
    if isinstance(repo, FakeRepo):
        repo.set_remote_url("origin", "https://example.invalid/second")
    else:
        git(tmp_path, "remote", "set-url", "origin", "https://example.invalid/second")
    second = repo.identity()
    assert first.origin_url == "https://example.invalid/first"
    assert second.origin_url == "https://example.invalid/second"
    assert before.key == first.key == second.key
    assert before.common_dir == first.common_dir == second.common_dir
