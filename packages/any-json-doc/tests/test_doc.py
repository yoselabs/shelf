"""Doc and DocSet through their public interface, on real files."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
from typing import TYPE_CHECKING, Any

import pytest

from any_json_doc import Absent, Doc, DocSet, ForeignVersion, ForeignVersionError, Present, RefusedError, Torn

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
    with pytest.raises(RefusedError, match=r"is v1, this install reads v2"):
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
    with pytest.raises(RefusedError, match=r"d\.json is torn"):
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
    docs = DocSet(tmp_path / "pins", ".json", _load)
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


@pytest.mark.parametrize("key", ["", ".hidden", "a/b"])
def test_docset_refuses_a_key_that_is_not_a_plain_stem(tmp_path: Path, key: str) -> None:
    with pytest.raises(ValueError, match="plain file stem"):
        DocSet(tmp_path).of(key)


def test_docset_refuses_a_suffix_that_is_not_an_extension(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="dot extension"):
        DocSet(tmp_path, "json")


_KILLED_WRITER = textwrap.dedent(
    """
    import os, sys, time
    from pathlib import Path
    from any_json_doc import Doc

    target, marker = Path(sys.argv[1]), Path(sys.argv[2])

    def stall(fd):  # the temp file is written and flushed; the replace has not happened yet
        marker.write_text("ready")
        time.sleep(60)

    os.fsync = stall
    Doc(target, fsync=True).write({"new": "x" * 100_000})
    """
)


def test_a_writer_killed_before_the_replace_leaves_the_old_document(tmp_path: Path) -> None:
    target, marker = tmp_path / "d.json", tmp_path / "ready"
    old = Doc(target)
    old.write({"old": True})
    child = subprocess.Popen([sys.executable, "-c", _KILLED_WRITER, str(target), str(marker)])
    try:
        deadline = time.monotonic() + 30
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists(), "child never reached the fsync"
        assert list(tmp_path.glob(".d.json.*.tmp")), "the child should be mid-write"
        os.kill(child.pid, signal.SIGKILL)
        child.wait(timeout=30)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
    assert old.read() == Present({"old": True})
    assert DocSet(tmp_path).keys() == ["d"]  # the leftover temp is no key
    old.write({"old": False})
    assert old.get() == {"old": False}
