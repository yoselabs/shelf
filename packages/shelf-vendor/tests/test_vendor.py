"""Vendor sync, drift check and newer-tag warning, against a throwaway shelf repository."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest

from shelf_vendor import Vendor, dir_files, newer_tags, tree_hash
from shelf_vendor.__main__ import main

if TYPE_CHECKING:
    from pathlib import Path


def _git(repo: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
        "HOME": str(repo),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin:" + os.environ.get("PATH", ""),
    }
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env).stdout.strip()


def _release(shelf: Path, body: str, tag: str) -> str:
    src = shelf / "packages" / "process-lock" / "src" / "process_lock"
    src.mkdir(parents=True, exist_ok=True)
    (src / "__init__.py").write_text(body, encoding="utf-8")
    _git(shelf, "add", "-A")
    _git(shelf, "commit", "-qm", tag)
    _git(shelf, "tag", tag)
    return _git(shelf, "rev-parse", "HEAD")


@pytest.fixture
def shelf(tmp_path: Path) -> Path:
    repo = tmp_path / "shelf"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _release(repo, "V = 1\n", "process-lock-v0.1.0")
    return repo


@pytest.fixture
def vendor(tmp_path: Path) -> Vendor:
    return Vendor(tmp_path / "skill" / "_vendor", tmp_path / "dev" / "vendor.json")


def test_tree_hash_is_order_free_and_content_sensitive() -> None:
    a = {"x.py": b"1", "y/z.py": b"2"}
    assert tree_hash(a) == tree_hash(dict(reversed(a.items())))
    assert tree_hash(a) != tree_hash({**a, "x.py": b"3"})
    assert tree_hash({"ab": b"c"}) != tree_hash({"a": b"bc"})


def test_sync_copies_the_tag_and_records_it(vendor: Vendor, shelf: Path) -> None:
    entry = vendor.sync("process-lock", "process-lock-v0.1.0", shelf=shelf)
    assert (vendor.vendor_dir / "process_lock" / "__init__.py").read_text(encoding="utf-8") == "V = 1\n"
    assert entry["name"] == "process_lock"
    assert entry["shelf_commit"] == _git(shelf, "rev-parse", "HEAD")
    assert vendor.load() == [entry]
    assert vendor.check(shelf) == ([], [])


def test_sync_reuses_the_recorded_tag_and_drops_removed_files(vendor: Vendor, shelf: Path) -> None:
    vendor.sync("process_lock", "process-lock-v0.1.0", shelf=shelf)
    (vendor.vendor_dir / "process_lock" / "stray.py").write_text("x", encoding="utf-8")
    vendor.sync("process_lock", shelf=shelf)
    assert sorted(dir_files(vendor.vendor_dir / "process_lock")) == ["__init__.py"]


def test_sync_without_any_tag_refuses(vendor: Vendor, shelf: Path) -> None:
    with pytest.raises(ValueError, match="no recorded tag"):
        vendor.sync("process-lock", shelf=shelf)


def test_edited_copy_is_drift(vendor: Vendor, shelf: Path) -> None:
    vendor.sync("process-lock", "process-lock-v0.1.0", shelf=shelf)
    (vendor.vendor_dir / "process_lock" / "__init__.py").write_text("V = 9\n", encoding="utf-8")
    drift, _ = vendor.check(shelf)
    assert len(drift) == 1 and "vendored tree hash" in drift[0]


def test_missing_copy_is_drift(vendor: Vendor, shelf: Path) -> None:
    vendor.sync("process-lock", "process-lock-v0.1.0", shelf=shelf)
    for p in sorted((vendor.vendor_dir / "process_lock").rglob("*"), reverse=True):
        p.unlink()
    (vendor.vendor_dir / "process_lock").rmdir()
    assert "is missing" in vendor.check()[0][0]


def test_manifest_hash_forged_is_caught_against_the_tag(vendor: Vendor, shelf: Path) -> None:
    vendor.sync("process-lock", "process-lock-v0.1.0", shelf=shelf)
    (vendor.vendor_dir / "process_lock" / "__init__.py").write_text("V = 9\n", encoding="utf-8")
    forged = [{**e, "tree_hash": tree_hash(dir_files(vendor.vendor_dir / "process_lock"))} for e in vendor.load()]
    vendor.manifest_path.write_text(__import__("json").dumps(forged), encoding="utf-8")
    drift, _ = vendor.check(shelf)
    assert len(drift) == 1 and "content hash" in drift[0]


def test_a_newer_tag_warns_without_drift(vendor: Vendor, shelf: Path) -> None:
    vendor.sync("process-lock", "process-lock-v0.1.0", shelf=shelf)
    _release(shelf, "V = 2\n", "process-lock-v0.2.0")
    _release(shelf, "V = 3\n", "process-lock-v0.10.0")
    drift, warnings = vendor.check(shelf)
    assert drift == []
    assert warnings == ["process_lock: newer shelf tag process-lock-v0.10.0 exists (recorded process-lock-v0.1.0)"]
    assert newer_tags(shelf, "process_lock", "process-lock-v0.10.0") == []


def test_a_recorded_bare_commit_warns_only_for_tags_it_lacks(vendor: Vendor, shelf: Path) -> None:
    commit = _git(shelf, "rev-parse", "HEAD")
    assert newer_tags(shelf, "process_lock", commit) == []
    _release(shelf, "V = 2\n", "process-lock-v0.2.0")
    assert newer_tags(shelf, "process_lock", commit) == ["process-lock-v0.2.0"]


def test_cli_sync_then_check(tmp_path: Path, shelf: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = ["--vendor-dir", str(tmp_path / "v"), "--manifest", str(tmp_path / "m.json"), "--shelf", str(shelf)]
    assert main([*base, "sync", "process-lock", "--tag", "process-lock-v0.1.0"]) == 0
    _release(shelf, "V = 2\n", "process-lock-v0.2.0")
    assert main([*base, "check"]) == 0
    err = capsys.readouterr().err
    assert "NEWER" in err and "DRIFT" not in err
    (tmp_path / "v" / "process_lock" / "__init__.py").write_text("x", encoding="utf-8")
    assert main([*base, "check"]) == 1
