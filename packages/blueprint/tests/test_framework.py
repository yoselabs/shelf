"""Framework concern: a Godot project found in a subfolder, judged from its profile with `{root}` and globs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo


def _godot(repo: Repo, root: str = "src/Game") -> None:
    repo.write(f"{root}/project.godot", 'config/features=PackedStringArray("4.7", "C#")\n')
    repo.write(f"{root}/Game.csproj", '<Project Sdk="Godot.NET.Sdk/4.7.2"></Project>\n')


def _rows(repo: Repo) -> dict[str, tuple[Verdict, str]]:
    return {r.id: (r.verdict, r.evidence) for r in run(repo.root, concern="framework", env=repo.env).rows}


def test_a_godot_project_in_a_subfolder_is_found_and_its_pin_read_through_a_glob(repo: Repo) -> None:
    _godot(repo)
    rows = _rows(repo)
    assert "in src/Game" in rows["framework.godot.profile"][1]
    assert rows["framework.godot.engine-version"][0] is Verdict.PASSING


def test_missing_godot_hygiene_is_not_set_up(repo: Repo) -> None:
    _godot(repo)
    assert _rows(repo)["framework.godot.project-hygiene"][0] is Verdict.NOT_SET_UP


def test_headless_build_outside_the_gate_fails(repo: Repo) -> None:
    _godot(repo)
    repo.write("Makefile", "check:\n\ttrue\nimport:\n\tgodot --headless --import --build-solutions\n")
    assert _rows(repo)["framework.godot.build"][0] is Verdict.FAILING


def test_two_projects_get_one_table_each_and_a_declared_one_wins(repo: Repo) -> None:
    _godot(repo)
    _godot(repo, "prototype/spike")
    ids = set(_rows(repo))
    assert {"framework.godot@src/Game.profile", "framework.godot@prototype/spike.profile"} <= ids
    repo.write("docs/blueprint/blueprint.toml", '[profile.frameworks]\ngodot = "src/Game"\n')
    assert "framework.godot.profile" in _rows(repo)


def test_no_framework_means_no_rows(repo: Repo) -> None:
    assert _rows(repo) == {}
