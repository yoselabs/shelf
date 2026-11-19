"""Legacy formats go through the LibreOffice found on the caller's PATH (``env``), never the process's."""

from __future__ import annotations

import os
import stat
from typing import TYPE_CHECKING

import docx as docx_writer
from convert_md import convert

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _fake_soffice(folder: Path, name: str, produced: Path) -> None:
    """A soffice that 'converts' by copying ``produced`` to <outdir>/<stem>.docx (argv: --headless --convert-to docx --outdir D FILE)."""
    folder.mkdir(parents=True, exist_ok=True)
    exe = folder / name
    exe.write_text(f'#!/bin/sh\ncp "{produced}" "$5/$(basename "$6" .doc).docx"\n')
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)


def _docx(path: Path) -> Path:
    doc = docx_writer.Document()
    doc.add_paragraph("Legacy body")
    doc.save(str(path))
    return path


def test_a_legacy_file_is_normalized_by_the_soffice_on_env_path(tmp_path: Path) -> None:
    _fake_soffice(tmp_path / "bin", "soffice", _docx(tmp_path / "made.docx"))
    old = tmp_path / "report.doc"
    old.write_bytes(b"not really a doc")
    result = convert(old, env={"PATH": str(tmp_path / "bin")})
    assert result.fidelity != "failed"
    assert "Legacy body" in result.body_markdown


def test_libreoffice_is_the_fallback_name(tmp_path: Path) -> None:
    _fake_soffice(tmp_path / "bin", "libreoffice", _docx(tmp_path / "made.docx"))
    old = tmp_path / "report.doc"
    old.write_bytes(b"x")
    assert "Legacy body" in convert(old, env={"PATH": str(tmp_path / "bin")}).body_markdown


def test_no_libreoffice_on_env_path_fails_even_when_the_process_path_has_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_soffice(tmp_path / "ambient", "soffice", _docx(tmp_path / "made.docx"))
    monkeypatch.setenv("PATH", f"{tmp_path / 'ambient'}{os.pathsep}{os.environ.get('PATH', '')}")
    old = tmp_path / "report.doc"
    old.write_bytes(b"x")
    result = convert(old, env={"PATH": str(tmp_path / "empty")})
    assert (result.fidelity, result.warnings) == ("failed", ["libreoffice_not_installed"])
