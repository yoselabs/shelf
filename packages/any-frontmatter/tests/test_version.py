"""Content-hash versions, and the write that refuses a stale one."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import pytest
from any_frontmatter import (
    Document,
    StaleVersionError,
    canonicalize,
    check_version,
    compute_version,
    read,
    version_of,
    version_of_file,
    write,
    write_checked,
)

if TYPE_CHECKING:
    from pathlib import Path


def _doc(fm: dict[str, object], body: str = "body\n") -> Document:
    return Document(frontmatter=dict(fm), body=body)


def test_a_version_is_64_hex() -> None:
    v = compute_version(_doc({"id": "1"}))
    assert len(v) == 64
    assert set(v) <= set("0123456789abcdef")


def test_layout_is_not_a_change() -> None:
    a = compute_version(_doc({"id": "1", "title": "X", "status": "open"}, body="a\nb\n"))
    b = compute_version(_doc({"status": "open", "title": "X", "id": "1"}, body="a\r\nb\r\n\n\n"))
    assert a == b


def test_content_is_a_change() -> None:
    assert compute_version(_doc({"id": "1"}, body="a\n")) != compute_version(_doc({"id": "1"}, body="b\n"))


def test_a_date_value_versions() -> None:
    assert canonicalize(_doc({"on": dt.date(2026, 1, 2)})).startswith('{"on": "2026-01-02"}')


def test_version_of_needs_no_document() -> None:
    assert version_of({"id": "1"}, "x") == compute_version(_doc({"id": "1"}, body="x\n"))


def test_a_matching_version_writes(tmp_path: Path) -> None:
    path = tmp_path / "e.md"
    write(path, _doc({"id": "1", "status": "open"}))
    expected = version_of_file(path)
    outcome = write_checked(path, merge=lambda cur: _doc({**cur.frontmatter, "status": "closed"}, cur.body), expected=expected)
    assert read(path).frontmatter["status"] == "closed"
    assert outcome.version == version_of_file(path) != expected


def test_no_expected_version_is_last_write_wins(tmp_path: Path) -> None:
    path = tmp_path / "e.md"
    write(path, _doc({"id": "1"}))
    outcome = write_checked(path, merge=lambda cur: _doc({**cur.frontmatter, "s": "x"}, cur.body))
    assert read(path).frontmatter["s"] == "x"
    assert outcome.version == version_of_file(path)


def test_a_missing_file_merges_from_empty(tmp_path: Path) -> None:
    path = tmp_path / "new.md"
    write_checked(path, merge=lambda cur: _doc({"seen": dict(cur.frontmatter)}, cur.body + "made\n"))
    assert read(path) == _doc({"seen": {}}, "made\n")


def test_a_stale_version_is_refused_and_the_file_untouched(tmp_path: Path) -> None:
    path = tmp_path / "e.md"
    write(path, _doc({"id": "1"}, body="other writer\n"))
    before = path.read_text(encoding="utf-8")
    with pytest.raises(StaleVersionError) as caught:
        write_checked(path, merge=lambda cur: _doc(cur.frontmatter, "mine\n"), expected="0" * 64)
    assert path.read_text(encoding="utf-8") == before
    assert (caught.value.expected, caught.value.actual, caught.value.path) == ("0" * 64, version_of_file(path), path)


def test_an_expected_version_of_a_missing_file_is_stale(tmp_path: Path) -> None:
    with pytest.raises(StaleVersionError) as caught:
        write_checked(tmp_path / "gone.md", merge=lambda cur: cur, expected="0" * 64)
    assert caught.value.actual is None


def _interloper(monkeypatch: pytest.MonkeyPatch, path: Path, theirs: Document, times: int) -> None:
    """Another writer lands right after each of the first ``times`` writes."""
    from any_frontmatter import version as version_module  # noqa: PLC0415

    left = [times]

    def write_then_lose(target: Path, doc: Document) -> None:
        write(target, doc)
        if left[0] > 0:
            left[0] -= 1
            write(path, theirs)

    monkeypatch.setattr(version_module, "write", write_then_lose)


def test_a_writer_that_slips_in_is_reported_not_overwritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "e.md"
    write(path, _doc({"n": 0}))
    expected = version_of_file(path)
    theirs = _doc({"n": 99}, "theirs\n")
    _interloper(monkeypatch, path, theirs, times=1)
    with pytest.raises(StaleVersionError) as caught:
        write_checked(path, merge=lambda cur: _doc({**cur.frontmatter, "mine": True}, cur.body), expected=expected)
    assert read(path) == theirs
    assert caught.value.actual == compute_version(theirs)


def test_a_writer_that_restores_the_base_is_retried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "e.md"
    base = _doc({"n": 0})
    write(path, base)
    _interloper(monkeypatch, path, base, times=1)
    outcome = write_checked(path, merge=lambda cur: _doc({**cur.frontmatter, "mine": True}, cur.body), expected=version_of_file(path))
    assert read(path).frontmatter["mine"] is True
    assert outcome.version == version_of_file(path)


def test_retries_are_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "e.md"
    base = _doc({"n": 0})
    write(path, base)
    _interloper(monkeypatch, path, base, times=10)
    with pytest.raises(StaleVersionError):
        write_checked(path, merge=lambda cur: _doc({**cur.frontmatter, "mine": True}, cur.body), expected=version_of_file(path), retries=2)


def test_check_version(tmp_path: Path) -> None:
    path = tmp_path / "e.md"
    write(path, _doc({"id": "1"}))
    check_version(path, version_of_file(path))
    with pytest.raises(StaleVersionError):
        check_version(path, "0" * 64)
