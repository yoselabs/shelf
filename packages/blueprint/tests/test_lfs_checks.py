"""LFS: a repo that declares LFS keeps every binary blob a pointer, and each clone has the LFS filter installed."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_POINTER = "version https://git-lfs.github.com/spec/v1\noid sha256:" + "a" * 64 + "\nsize 3\n"
_BINARY = b"\x89PNG\r\n\x1a\n\x00\x00\x00binary"


@pytest.fixture(autouse=True)
def _no_user_git_config(monkeypatch: pytest.MonkeyPatch) -> None:
    # A `git lfs install` in the developer's global config would turn every fixture binary into a real pointer.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _rows(repo: Repo, *, audit: bool = False) -> dict[str, tuple[Verdict, str]]:
    repo.env |= {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    report = run(repo.root, concern="gate", audit=audit, env=repo.env)
    return {r.id: (r.verdict, r.evidence) for r in report.rows if r.id.startswith("gate.lfs")}


def _lfs_repo(repo: Repo) -> None:
    repo.write(".gitattributes", "*.png filter=lfs diff=lfs merge=lfs -text\n")
    # A filter that stores what it is given, so the index holds exactly the bytes the test writes.
    repo.git("config", "filter.lfs.clean", "cat")
    repo.git("config", "filter.lfs.smudge", "cat")


def test_a_repo_without_lfs_is_not_judged_for_it(repo: Repo) -> None:
    (repo.root / "logo.png").write_bytes(_BINARY)
    repo.commit()
    assert {v for v, _ in _rows(repo, audit=True).values()} == {Verdict.NOT_APPLICABLE}


def test_pointers_under_lfs_patterns_pass(repo: Repo) -> None:
    _lfs_repo(repo)
    repo.write("art/logo.png", _POINTER)
    repo.commit()
    assert _rows(repo)["gate.lfs-binaries"][0] is Verdict.PASSING


def test_a_binary_no_pattern_covers_fails(repo: Repo) -> None:
    _lfs_repo(repo)
    (repo.root / "clip.mp4").write_bytes(_BINARY)
    repo.commit()
    verdict, evidence = _rows(repo)["gate.lfs-binaries"]
    assert verdict is Verdict.FAILING
    assert "clip.mp4" in evidence
    assert "no LFS pattern" in evidence


def test_a_binary_committed_raw_under_an_lfs_pattern_fails(repo: Repo) -> None:
    # The clone had no LFS filter: git stored the bytes, not a pointer.
    _lfs_repo(repo)
    (repo.root / "logo.png").write_bytes(_BINARY)
    repo.commit()
    verdict, evidence = _rows(repo)["gate.lfs-binaries"]
    assert verdict is Verdict.FAILING
    assert "logo.png" in evidence
    assert "raw" in evidence


def test_a_clone_without_the_lfs_filter_fails_the_audit(repo: Repo) -> None:
    repo.write(".gitattributes", "*.png filter=lfs diff=lfs merge=lfs -text\n")
    repo.fake_tool(repo.bin_dir / "git-lfs", "git-lfs/3.7.1 (GitHub; linux amd64)")
    verdict, evidence = _rows(repo, audit=True)["gate.lfs-installed"]
    assert verdict is Verdict.FAILING
    assert "git lfs install" in evidence


def test_a_clone_with_the_filter_and_git_lfs_passes_the_audit(repo: Repo) -> None:
    repo.write(".gitattributes", "*.png filter=lfs diff=lfs merge=lfs -text\n")
    repo.git("config", "filter.lfs.process", "git-lfs filter-process")
    repo.git("config", "filter.lfs.required", "true")
    repo.fake_tool(repo.bin_dir / "git-lfs", "git-lfs/3.7.1 (GitHub; linux amd64)")
    assert _rows(repo, audit=True)["gate.lfs-installed"][0] is Verdict.PASSING


def test_the_installed_filter_is_audit_only(repo: Repo) -> None:
    _lfs_repo(repo)
    assert "gate.lfs-installed" not in _rows(repo)


def test_a_missing_git_lfs_is_fixed_through_the_system_package_manager_not_mise(repo: Repo) -> None:
    repo.write(".gitattributes", "*.png filter=lfs diff=lfs merge=lfs -text\n")
    repo.env["PATH"] = "/nonexistent"
    verdict, remediation = next(
        (r.verdict, r.remediation) for r in run(repo.root, concern="gate", audit=True, env=repo.env).rows if r.id == "gate.lfs-installed"
    )
    assert verdict is Verdict.NOT_SET_UP
    assert "system package manager" in remediation
