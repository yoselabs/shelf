from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from sqlite_store import clear_filesystem_cache, filesystem_allowed
from sqlite_store import filesystem as fs

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def clear_cache() -> Generator[None]:
    clear_filesystem_cache()
    yield
    clear_filesystem_cache()


def test_verdict_cached_cleared_and_invalidated_after_fork(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    probe = Mock(return_value=False)
    monkeypatch.setattr(fs, "_unsafe_filesystem", probe)
    assert filesystem_allowed(tmp_path)
    assert filesystem_allowed(tmp_path)
    probe.assert_called_once_with(tmp_path)
    clear_filesystem_cache()
    assert filesystem_allowed(tmp_path)
    assert probe.call_count == 2
    pid = os.getpid()
    monkeypatch.setattr(os, "getpid", lambda: pid + 1)
    assert filesystem_allowed(tmp_path)
    assert probe.call_count == 3


def test_detection_failures_are_not_cached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    probe = Mock(side_effect=[None, False, True])
    monkeypatch.setattr(fs, "_unsafe_filesystem", probe)
    assert not filesystem_allowed(tmp_path)
    assert filesystem_allowed(tmp_path)
    clear_filesystem_cache()
    assert not filesystem_allowed(tmp_path)
    assert not filesystem_allowed(tmp_path)
    assert probe.call_count == 3


@pytest.mark.parametrize("fstype,allowed", [("ext4", True), ("nfs4", False), ("cifs", False), ("fuse.sshfs", False), ("SMB", False)])
def test_filesystem_types(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fstype: str, allowed: bool) -> None:
    monkeypatch.setattr(fs, "_filesystem_type", lambda _path: fstype)
    assert filesystem_allowed(tmp_path) is allowed


def test_linux_deepest_mount_decodes_spaces(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fs.sys, "platform", "linux")
    mounts = "root / ext4 rw 0 0\nremote /mnt nfs rw 0 0\nlocal /mnt/a\\040b ext4 rw 0 0\n"
    monkeypatch.setattr(Path, "read_text", lambda *_args, **_kwargs: mounts)
    assert fs._filesystem_type(Path("/mnt/elsewhere")) == "nfs"
    assert fs._filesystem_type(Path("/mnt/a b/nested")) == "ext4"


def test_unknown_type_rejects_mounts_below_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fs.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "is_mount", lambda path: path in {Path("/"), Path("/Volumes/network")})
    assert not filesystem_allowed(Path("/Volumes/network/nested"))
    assert filesystem_allowed(Path("/Users/local"))


def test_probe_errors_refuse_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_path: Path) -> str:
        raise OSError

    monkeypatch.setattr(fs, "_filesystem_type", fail)
    assert not filesystem_allowed(tmp_path)
