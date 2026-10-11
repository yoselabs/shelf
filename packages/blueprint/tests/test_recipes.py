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


def _run(recipe: str, args: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    # Loaded from its file, the way a repo runs its copy; in-process, so coverage sees it.
    spec = importlib.util.spec_from_file_location(recipe.replace("-", "_"), RECIPES / RECIPE_FILES[recipe])
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    code = module.main(args)
    return code, capsys.readouterr().out


def _integrity(repo: Repo, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    return _run("unity-integrity", [str(repo.root)], capsys)


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


def _coverage(repo: Repo, line: float, branch: float, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    summary = repo.write("cov/Summary.json", f'{{"summary": {{"linecoverage": {line}, "branchcoverage": {branch}}}}}')
    floor = repo.write("coverage-floor.json", '{"line": 89.0, "branch": 75.0}')
    return _run("dotnet-coverage", [str(summary), str(floor)], capsys)


def test_the_coverage_floor_passes_at_or_over_the_floor(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = _coverage(repo, 89.9, 75.0, capsys)
    assert code == 0
    assert "line 89.9% (floor 89.0%)" in out


def test_the_coverage_floor_fails_under_it_and_names_the_metric(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = _coverage(repo, 91.0, 74.2, capsys)
    assert code == 1
    assert "branch coverage 74.2% < floor 75.0%" in out
    assert "line coverage" not in out.split("below floor")[-1]


_UID = "uid://b1"


def _godot_project(repo: Repo) -> None:
    repo.write("project.godot", 'config/features=PackedStringArray("4.7", "C#")\n')
    repo.write("Game.csproj", '<Project Sdk="Godot.NET.Sdk/4.7.2"></Project>\n')
    repo.write("Panel.cs", "partial class Panel {}\n")
    repo.write("Panel.cs.uid", f"{_UID}\n")
    repo.write(
        "Main.tscn",
        '[gd_scene load_steps=2 format=3 uid="uid://m1"]\n\n'
        f'[ext_resource type="Script" uid="{_UID}" path="res://Panel.cs" id="1_a"]\n\n'
        '[node name="Main" type="Control"]\nscript = ExtResource("1_a")\n',
    )


def test_the_godot_check_passes_a_clean_project(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _godot_project(repo)
    assert _run("godot-integrity", [str(repo.root)], capsys) == (0, "godot surface: clean\n")


def test_the_godot_check_fails_where_the_import_log_stays_quiet(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _godot_project(repo)
    (repo.root / "Panel.cs.uid").unlink()
    repo.write("Other.tscn", '[gd_scene format=3]\n\n[ext_resource type="Script" path="res://Gone.cs" id="1_b"]\ngarbage here\n')
    repo.write("Game.csproj", '<Project Sdk="Godot.NET.Sdk/4.6.1"></Project>\n')
    code, out = _run("godot-integrity", [str(repo.root)], capsys)
    assert code == 1
    for needle in ("Panel.cs has no committed .uid", "does not exist", "not a section", "never used", "says Godot.NET.Sdk 4.6"):
        assert needle in out, needle
