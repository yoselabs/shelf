"""What a file's name and bytes say (moved from a2kay tests/core/test_attachments.py; the
media-type cases are new and pin a2kay-6cqa: no answer may depend on the host's mime.types)."""

from __future__ import annotations

import mimetypes
import unicodedata
from pathlib import Path

import any_file
import pytest
from any_file import (
    OCTET_STREAM,
    REGISTERED_TYPES,
    AnyFileError,
    PathEscapeError,
    UnsafeNameError,
    is_text_media,
    looks_binary,
    media_type,
    name_collision,
    resolve_within,
    safe_name,
)

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_a_plain_basename_is_kept() -> None:
    assert safe_name("estimate.xlsx") == "estimate.xlsx"
    assert safe_name("mic.wav") == "mic.wav"


@pytest.mark.parametrize("bad", ["", ".", "..", "a/b.txt", "../evil", "sub/dir/x", "foo/", "/abs.txt", "a\\b.txt"])
def test_traversal_and_separators_are_refused(bad: str) -> None:
    with pytest.raises(UnsafeNameError) as caught:
        safe_name(bad)
    assert caught.value.value == bad
    assert isinstance(caught.value, AnyFileError)


def test_a_decomposed_name_comes_back_composed() -> None:
    decomposed = unicodedata.normalize("NFD", "Résumé.pdf")
    assert decomposed != "Résumé.pdf"
    assert safe_name(decomposed) == unicodedata.normalize("NFC", "Résumé.pdf")


def test_resolve_within_returns_the_in_tree_path(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    (root / "sub").mkdir(parents=True)
    resolved = resolve_within(root, "sub/file.txt")
    assert resolved == (root / "sub" / "file.txt").resolve()
    assert resolve_within(root, Path("sub") / "x.pdf") == (root / "sub" / "x.pdf").resolve()


@pytest.mark.parametrize("ref", ["../../etc/passwd", "/etc/passwd", "sub/../../x"])
def test_resolve_within_refuses_an_escape(tmp_path: Path, ref: str) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    with pytest.raises(PathEscapeError) as caught:
        resolve_within(root, ref)
    assert caught.value.value == ref


def test_resolve_within_follows_a_symlink_out(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "link").symlink_to(tmp_path)
    with pytest.raises(PathEscapeError):
        resolve_within(root, "link/secret")


def test_looks_binary_reads_a_nul_in_the_first_8_kib() -> None:
    assert looks_binary(b"a,b\n\x00c")
    assert not looks_binary("naïve,café\n".encode())
    assert not looks_binary(b"x" * 8192 + b"\x00")  # past the sniffed head


def test_name_collision_finds_case_and_normalization_twins() -> None:
    existing = ["Report.pdf", unicodedata.normalize("NFC", "Résumé.pdf")]
    assert name_collision(existing, "report.pdf") == "Report.pdf"
    assert name_collision(existing, unicodedata.normalize("NFD", "RÉSUMÉ.pdf")) is not None
    assert name_collision(existing, "Report.pdf") is None  # the same name is the same file
    assert name_collision(existing, "other.pdf") is None


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("budget.xlsx", _XLSX),
        ("Letter.DOCX", _DOCX),
        ("deck.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ("notes.odt", "application/vnd.oasis.opendocument.text"),
        ("calls.jsonl", "application/x-ndjson"),
        ("calls.ndjson", "application/x-ndjson"),
        ("config.yml", "application/yaml"),
        ("voice.m4a", "audio/mp4"),
        ("photo.webp", "image/webp"),
        ("report.pdf", "application/pdf"),
        ("mic.wav", "audio/x-wav"),
        ("notes.md", "text/markdown"),
        ("data.csv", "text/csv"),
        ("genome.vcf.gz", "text/x-vcard"),
        ("noext", OCTET_STREAM),
        ("thing.unknownext", OCTET_STREAM),
    ],
)
def test_media_type_reads_the_extension(name: str, expected: str) -> None:
    assert media_type(name) == expected


def test_a_declared_media_type_wins() -> None:
    assert media_type("x.bin", declared="image/png") == "image/png"
    assert media_type("x.pdf", declared="") == "application/pdf"


def test_media_type_does_not_read_the_hosts_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """a2kay-6cqa: python:3.12-slim has no /etc/mime.types, so the module-level guess knew no
    .xlsx and the attachment was refused. Blind every host-dependent path; the answer holds."""
    monkeypatch.setattr(mimetypes, "knownfiles", [])
    monkeypatch.setattr(mimetypes, "guess_type", lambda *_a, **_k: (None, None))
    monkeypatch.setattr(mimetypes, "types_map", {})
    monkeypatch.setattr(mimetypes.MimeTypes, "read", lambda *_a, **_k: pytest.fail("a host file was read"))
    any_file._table.cache_clear()
    try:
        assert media_type("budget.xlsx") == _XLSX
        assert media_type("letter.docx") == _DOCX
        assert media_type("report.pdf") == "application/pdf"
        assert media_type("talk.mpga") == "audio/mpeg"
        assert media_type("note.amr") == "audio/amr"
        assert media_type("memo.caf") == "audio/x-caf"  # codespell:ignore caf
        assert media_type("clip.wmv") == "video/x-ms-wmv"
        assert media_type("scan.psd") == "image/vnd.adobe.photoshop"
        assert media_type("main.cpp") == "text/x-c"
        for ext, media in REGISTERED_TYPES.items():
            assert media_type(f"x{ext}") == media, ext
    finally:
        any_file._table.cache_clear()


@pytest.mark.parametrize(
    ("media", "text"),
    [
        ("text/plain", True),
        ("text/csv", True),
        ("application/json", True),
        ("application/x-ndjson", True),
        ("application/yaml", True),
        ("application/pdf", False),
        ("image/png", False),
        (None, False),
    ],
)
def test_is_text_media(media: str | None, text: bool) -> None:
    assert is_text_media(media) is text
