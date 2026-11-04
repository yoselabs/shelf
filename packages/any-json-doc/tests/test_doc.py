"""Doc and DocSet through their public interface, on real files."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

import pytest

from any_json_doc import Absent, Doc, DocSet, ForeignVersion, ForeignVersionError, Present, Refused, Torn

if TYPE_CHECKING:
    from pathlib import Path

WANT = 2


def _load(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or "n" not in data:
        msg = "not a record"
        raise ValueError(msg)
    if data.get("v") != WANT:
        raise ForeignVersionError(data.get("v"), WANT)
    return data


def _doc(tmp_path: Path) -> Doc[dict[str, Any]]:
    return Doc(tmp_path / "d.json", _load)


def test_absent_when_no_file(tmp_path: Path) -> None:
    doc = _doc(tmp_path)
    assert doc.read() == Absent()
    assert doc.get() is None
    assert doc.need() is None


def test_present_after_write_then_absent_after_delete(tmp_path: Path) -> None:
    doc = _doc(tmp_path / "nested")
    doc.write({"v": WANT, "n": 1})
    assert doc.read() == Present({"v": WANT, "n": 1})
    assert doc.need() == {"v": WANT, "n": 1}
    doc.delete()
    doc.delete()  # deleting nothing is fine
    assert doc.read() == Absent()


def test_default_codec_is_raw_json(tmp_path: Path) -> None:
    doc: Doc[Any] = Doc(tmp_path / "raw.json")
    doc.write([1, "é"])
    assert doc.get() == [1, "é"]


def test_foreign_version_is_never_read_as_empty(tmp_path: Path) -> None:
    doc = _doc(tmp_path)
    doc.path.write_text('{"v": 1, "n": 1}', encoding="utf-8")
    assert doc.read() == ForeignVersion(doc.path, 1, WANT)
    assert doc.get() is None
    with pytest.raises(Refused, match=r"is v1, this install reads v2"):
        doc.need()


@pytest.mark.parametrize(
    "bytes_",
    [b'{"v": 2, "n"', b"", b"not json", b"[1, 2]", b"\xff\xfe\x00"],
    ids=["half-written", "empty", "garbage", "wrong-shape", "not-utf8"],
)
def test_torn_file_is_named_and_refused(tmp_path: Path, bytes_: bytes) -> None:
    doc = _doc(tmp_path)
    doc.path.write_bytes(bytes_)
    assert isinstance(doc.read(), Torn)
    assert doc.get() is None
    with pytest.raises(Refused, match=r"d\.json is torn"):
        doc.need()


def test_unreadable_path_is_torn(tmp_path: Path) -> None:
    (tmp_path / "d.json").mkdir()
    assert isinstance(_doc(tmp_path).read(), Torn)


def test_torn_write_from_a_killed_writer_leaves_the_old_document(tmp_path: Path) -> None:
    doc = _doc(tmp_path)
    doc.write({"v": WANT, "n": 1})
    leftover = tmp_path / ".d.json.abc123.tmp"  # what a writer killed between temp-write and replace leaves
    leftover.write_bytes(b'{"v": 2, "n"')
    assert doc.read() == Present({"v": WANT, "n": 1})
    doc.write({"v": WANT, "n": 2})
    assert doc.get() == {"v": WANT, "n": 2}


def test_a_concurrent_reader_never_sees_a_half_written_document(tmp_path: Path) -> None:
    doc = _doc(tmp_path)
    blob = "x" * 200_000
    doc.write({"v": WANT, "n": 0, "blob": blob})
    stop = threading.Event()

    def writer() -> None:
        n = 0
        while not stop.is_set():
            n += 1
            doc.write({"v": WANT, "n": n, "blob": blob})

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        seen = [doc.read() for _ in range(300)]
    finally:
        stop.set()
        thread.join()
    assert all(isinstance(r, Present) for r in seen)


def test_docset_keeps_one_document_per_key(tmp_path: Path) -> None:
    docs = DocSet(lambda key: tmp_path / "pins" / f"{key}.json", _load)
    assert docs.keys() == []
    docs.of("b").write({"v": WANT, "n": 2})
    docs.of("a").write({"v": WANT, "n": 1})
    (tmp_path / "pins" / ".a.json.zz.tmp").write_text("{", encoding="utf-8")
    (tmp_path / "pins" / ".hidden.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pins" / "other.txt").write_text("x", encoding="utf-8")
    assert docs.keys() == ["a", "b"]
    assert docs.of("a").get() == {"v": WANT, "n": 1}
    docs.of("a").delete()
    assert docs.keys() == ["b"]
