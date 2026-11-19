"""missing_engines — packaging drift is caught before a file converts to `failed`."""

from __future__ import annotations

import ast
import inspect
from typing import TYPE_CHECKING

import pytest
from convert_md import dispatch, engines, missing_engines

if TYPE_CHECKING:
    from pathlib import Path

_ENGINES = [
    engines.PymupdfLlmEngine,
    engines.MammothEngine,
    engines.MarkitdownEngine,
    engines.OpenpyxlEngine,
    engines.TrafilaturaEngine,
    engines.Html2TextEngine,
]


def test_the_dev_environment_has_every_document_engine() -> None:
    assert missing_engines([".pdf", ".docx", ".pptx", ".xlsx", ".html"], env={}) == {}


def test_suffix_spelling_is_forgiving() -> None:
    assert missing_engines(["PDF", "docx"], env={}) == {}


def test_an_unsupported_format_is_reported() -> None:
    assert missing_engines([".odt"], env={}) == {".odt": ["no engine chain"]}


def test_a_missing_library_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dispatch, "_installed", lambda module: module != "mammoth")
    assert missing_engines([".docx", ".pdf"], env={}) == {".docx": ["MammothEngine: module 'mammoth' not installed"]}


def test_a_legacy_format_needs_libreoffice_on_the_given_path(tmp_path: Path) -> None:
    assert missing_engines([".doc"], env={"PATH": str(tmp_path)}) == {".doc": ["libreoffice not on PATH"]}
    for name in ("libreoffice", "soffice"):
        exe = tmp_path / name
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        assert missing_engines([".doc"], env={"PATH": str(tmp_path)}) == {}
        exe.unlink()


def test_nothing_is_imported_to_check(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(name: str, *args: object, **kwargs: object) -> object:
        msg = f"imported {name}"
        raise AssertionError(msg)

    monkeypatch.setattr("builtins.__import__", refuse)
    assert missing_engines([".pdf"], env={}) == {}


@pytest.mark.parametrize("engine", _ENGINES, ids=lambda e: e.__name__)
def test_declared_modules_match_what_convert_imports(engine: type) -> None:
    """`modules` is a declaration next to the code it describes; this keeps them equal."""
    tree = ast.parse(inspect.getsource(engine))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    imported.discard("convert_md")
    assert set(engine.modules) == imported
