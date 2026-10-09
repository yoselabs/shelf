"""dir-trust: machine-local, content-hashed, revoked by any edit."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest
from dir_trust import TrustStore, TrustStoreError, folder_hash

if TYPE_CHECKING:
    from pathlib import Path


def _file(folder: Path, name: str, content: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(content, encoding="utf-8")


@pytest.fixture
def setup(tmp_path: Path) -> tuple[Path, Path, TrustStore]:
    key = tmp_path / "vault"
    folder = key / "jobs"
    _file(folder, "a.py", "def run(ctx): ...\n")
    return key, folder, TrustStore(tmp_path / "config" / "trust.yml")


def test_grant_then_trusted(setup: tuple[Path, Path, TrustStore]) -> None:
    key, folder, store = setup
    assert store.is_trusted(key, folder, pattern="*.py") is False
    store.grant(key, folder, pattern="*.py")
    assert store.is_trusted(key, folder, pattern="*.py") is True


def test_store_written_where_asked_not_in_the_folder(setup: tuple[Path, Path, TrustStore]) -> None:
    key, folder, store = setup
    store.grant(key, folder, pattern="*.py")
    assert store.path.exists()
    assert not any(p.name == "trust.yml" for p in key.rglob("*"))


def test_editing_a_file_revokes(setup: tuple[Path, Path, TrustStore]) -> None:
    key, folder, store = setup
    store.grant(key, folder, pattern="*.py")
    _file(folder, "a.py", "def run(ctx):\n    do_something_new()\n")
    assert store.is_trusted(key, folder, pattern="*.py") is False


def test_adding_a_file_revokes(setup: tuple[Path, Path, TrustStore]) -> None:
    key, folder, store = setup
    store.grant(key, folder, pattern="*.py")
    _file(folder, "b.py", "def run(ctx): ...\n")
    assert store.is_trusted(key, folder, pattern="*.py") is False


def test_removing_a_file_revokes(setup: tuple[Path, Path, TrustStore]) -> None:
    key, folder, store = setup
    _file(folder, "b.py", "x\n")
    store.grant(key, folder, pattern="*.py")
    (folder / "b.py").unlink()
    assert store.is_trusted(key, folder, pattern="*.py") is False


def test_a_file_outside_the_pattern_does_not_count(setup: tuple[Path, Path, TrustStore]) -> None:
    key, folder, store = setup
    store.grant(key, folder, pattern="*.py")
    _file(folder, "notes.md", "anything\n")
    assert store.is_trusted(key, folder, pattern="*.py") is True


def test_revoke(setup: tuple[Path, Path, TrustStore]) -> None:
    key, folder, store = setup
    store.grant(key, folder, pattern="*.py")
    assert store.revoke(key) is True
    assert store.is_trusted(key, folder, pattern="*.py") is False
    assert store.revoke(key) is False


def test_key_is_resolved(setup: tuple[Path, Path, TrustStore]) -> None:
    key, folder, store = setup
    store.grant(key / "jobs" / "..", folder, pattern="*.py")
    assert store.is_trusted(key, folder, pattern="*.py") is True


def test_grants_for_other_keys_survive(tmp_path: Path) -> None:
    store = TrustStore(tmp_path / "trust.yml")
    a, b = tmp_path / "a", tmp_path / "b"
    _file(a, "x.py", "1")
    _file(b, "x.py", "2")
    store.grant(a, a, pattern="*.py")
    store.grant(b, b, pattern="*.py")
    store.revoke(a)
    assert store.is_trusted(b, b, pattern="*.py") is True


def test_hash_is_order_independent(tmp_path: Path) -> None:
    folder = tmp_path / "jobs"
    _file(folder, "z.py", "z\n")
    _file(folder, "a.py", "a\n")
    h1 = folder_hash(folder, "*.py")
    (folder / "a.py").write_text("a\n", encoding="utf-8")
    assert folder_hash(folder, "*.py") == h1


def test_hash_digest_is_fixed(tmp_path: Path) -> None:
    """The digest is part of the contract: a changed algorithm revokes every grant on disk."""
    folder = tmp_path / "jobs"
    _file(folder, "b.py", "bb")
    _file(folder, "a.py", "aa")
    expected = hashlib.sha256(b"a.py\0aa\0b.py\0bb\0").hexdigest()
    assert folder_hash(folder, "*.py") == expected


def test_moving_bytes_between_files_changes_the_hash(tmp_path: Path) -> None:
    one, two = tmp_path / "one", tmp_path / "two"
    _file(one, "a", "xy")
    _file(one, "b", "")
    _file(two, "a", "x")
    _file(two, "b", "y")
    assert folder_hash(one) != folder_hash(two)


def test_missing_and_empty_folders_share_one_digest(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    assert folder_hash(tmp_path / "missing") == folder_hash(tmp_path / "empty") == hashlib.sha256().hexdigest()


def test_a_folder_matching_the_pattern_is_skipped(tmp_path: Path) -> None:
    folder = tmp_path / "jobs"
    _file(folder, "a.py", "a")
    before = folder_hash(folder, "*.py")
    (folder / "pkg.py").mkdir()
    assert folder_hash(folder, "*.py") == before


def test_store_reads_existing_yaml_layout(tmp_path: Path) -> None:
    """A store written by an earlier version — a plain YAML mapping — still reads."""
    key = tmp_path / "vault"
    folder = key / "jobs"
    _file(folder, "a.py", "a")
    path = tmp_path / "trust.yml"
    path.write_text(f"{key.resolve()}: {folder_hash(folder, '*.py')}\n", encoding="utf-8")
    assert TrustStore(path).is_trusted(key, folder, pattern="*.py") is True


def test_a_store_that_is_not_a_mapping_is_empty(tmp_path: Path) -> None:
    path = tmp_path / "trust.yml"
    path.write_text("- just\n- a list\n", encoding="utf-8")
    assert TrustStore(path).is_trusted(tmp_path, tmp_path) is False


def test_an_unparseable_store_raises_naming_it(tmp_path: Path) -> None:
    path = tmp_path / "trust.yml"
    path.write_text("key: [unclosed\n", encoding="utf-8")
    with pytest.raises(TrustStoreError) as caught:
        TrustStore(path).is_trusted(tmp_path, tmp_path)
    assert caught.value.path == path


def test_an_unwritable_store_raises(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")
    store = TrustStore(blocker / "trust.yml")
    with pytest.raises(TrustStoreError):
        store.grant(tmp_path, tmp_path)
