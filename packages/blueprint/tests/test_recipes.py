"""Recipes: files `blueprint recipe <name>` prints for a repo to copy and own (ADR 0004)."""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING

from blueprint.__main__ import RECIPE_FILES, RECIPES, main

if TYPE_CHECKING:
    import pytest
    from blueprint.testing import Repo

_GUID = "0123456789abcdef0123456789abcdef"


def test_every_recipe_prints_its_file(capsys: pytest.CaptureFixture[str]) -> None:
    for name, file in RECIPE_FILES.items():
        assert main(["recipe", name]) == 0
        assert capsys.readouterr().out == (RECIPES / file).read_text()


def _integrity(repo: Repo, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    # Loaded from its file, the way a repo runs its copy; in-process, so coverage sees it.
    spec = importlib.util.spec_from_file_location("unity_integrity", RECIPES / RECIPE_FILES["unity-integrity"])
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    code = module.main([str(repo.root)])
    return code, capsys.readouterr().out


def _clean_unity(repo: Repo) -> None:
    repo.write("ProjectSettings/EditorSettings.asset", "  m_SerializationMode: 2\n")
    repo.write("ProjectSettings/VersionControlSettings.asset", "  m_Mode: Visible Meta Files\n")
    repo.write("Assets/Player.cs", "class Player {}\n")
    repo.write("Assets/Player.cs.meta", f"guid: {_GUID}\n")


def test_the_unity_integrity_script_passes_a_clean_project(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _clean_unity(repo)
    assert _integrity(repo, capsys) == (0, "")


def test_the_unity_integrity_script_fails_on_each_broken_rule(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _clean_unity(repo)
    repo.write("Assets/Enemy.cs", "class Enemy {}\n")
    repo.write("Assets/Gone.cs.meta", f"guid: {_GUID}\n")
    repo.write("ProjectSettings/EditorSettings.asset", "  m_SerializationMode: 0\n")
    code, out = _integrity(repo, capsys)
    assert code == 1
    for needle in ("asset without .meta: Assets/Enemy.cs", "orphan meta", "duplicate guid", "Force Text"):
        assert needle in out, needle
