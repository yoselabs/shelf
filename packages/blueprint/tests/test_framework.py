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
    assert rows["framework.godot.framework-version"][0] is Verdict.PASSING


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


_SERVER = "from fastmcp import FastMCP\n\nmcp = FastMCP('demo')\n"
_CLIENT = "from fastmcp import Client\n\nclient = Client('http://localhost/mcp')\n"
_DEPENDS = 'dependencies = ["fastmcp>=3.4,<4"]'


def _mcp(repo: Repo, *, dependency: str = _DEPENDS, source: str = _SERVER, root: str = ".") -> None:
    prefix = "" if root == "." else f"{root}/"
    repo.write(f"{prefix}pyproject.toml", f'[project]\nname = "demo"\nversion = "0"\n{dependency}\n')
    repo.write(f"{prefix}src/demo/server.py", source)


def test_a_fastmcp_server_is_detected_from_its_dependency_and_its_use(repo: Repo) -> None:
    _mcp(repo)
    rows = _rows(repo)
    assert "in ." in rows["framework.mcp.profile"][1]
    assert "framework.mcp.surface-integrity" in rows


def test_a_server_in_a_subfolder_gets_its_folder_as_root(repo: Repo) -> None:
    _mcp(repo, root="services/tools")
    assert "in services/tools" in _rows(repo)["framework.mcp.profile"][1]


def test_an_optional_dependency_counts_and_the_slim_package_too(repo: Repo) -> None:
    _mcp(repo, dependency='[project.optional-dependencies]\nserve = ["FastMCP_slim>=4"]')
    assert "framework.mcp.profile" in _rows(repo)


def test_a_client_only_repo_is_not_an_mcp_server(repo: Repo) -> None:
    _mcp(repo, source=_CLIENT)
    assert _rows(repo) == {}


def test_a_dev_group_dependency_is_a_test_client_not_a_server(repo: Repo) -> None:
    _mcp(repo, dependency='[dependency-groups]\ndev = ["fastmcp>=3"]')
    assert _rows(repo) == {}


def test_a_throwaway_server_in_tests_does_not_make_a_server(repo: Repo) -> None:
    _mcp(repo, source=_CLIENT)
    repo.write("tests/test_client.py", _SERVER)
    assert _rows(repo) == {}


def test_a_declared_framework_wins_over_detection(repo: Repo) -> None:
    _mcp(repo)
    repo.write("docs/blueprint/blueprint.toml", '[profile.frameworks]\nmcp = "elsewhere"\n')
    assert "in elsewhere" in _rows(repo)["framework.mcp.profile"][1]


def test_a_declared_framework_is_judged_even_when_nothing_is_detected(repo: Repo) -> None:
    _mcp(repo, source=_CLIENT)
    repo.write("docs/blueprint/blueprint.toml", '[profile.frameworks]\nmcp = "."\n')
    assert "framework.mcp.profile" in _rows(repo)


def _a2kay_shaped(repo: Repo) -> None:
    _mcp(repo, dependency=_DEPENDS + '\n[tool.ruff.lint]\nselect = ["T20"]')
    repo.write("uv.lock", '[[package]]\nname = "fastmcp"\n')
    repo.write("tests/test_server.py", "async def t(c):\n    r = await c.initialize_result\n    assert Client(s) and r.is_error\n")
    repo.write("tests/test_stdio.py", "t = StdioTransport\n")
    repo.write("tests/contracts/test_tool_list.py", "tools = list_tools()\nhint = 'readOnlyHint'\n")
    repo.write("tests/contracts/tools.snapshot.json", "[]\n")
    repo.write("Makefile", "check:\n\tuv run pytest\n")


def test_a_repo_shaped_like_a2kay_passes_the_configured_roles(repo: Repo) -> None:
    _a2kay_shaped(repo)
    rows = _rows(repo)
    for role in ("framework-version", "project-hygiene", "build", "tests", "surface-integrity"):
        assert rows[f"framework.mcp.{role}"][0] is Verdict.PASSING, role
    assert rows["framework.mcp.agent-guidance"][0] is Verdict.NOT_SET_UP


def test_a_server_without_a_tool_list_snapshot_is_not_set_up(repo: Repo) -> None:
    _a2kay_shaped(repo)
    (repo.root / "tests/contracts/tools.snapshot.json").unlink()
    assert _rows(repo)["framework.mcp.surface-integrity"][0] is Verdict.NOT_SET_UP


def test_the_framework_layer_shows_in_the_report(repo: Repo) -> None:
    _mcp(repo)
    report = run(repo.root, concern="framework", env=repo.env)
    assert report.rows
    assert {r.layer for r in report.rows} == {"framework"}


def _unity(repo: Repo, root: str = "Game") -> None:
    repo.write(f"{root}/ProjectSettings/ProjectVersion.txt", "m_EditorVersion: 6000.3.2f1\n")
    repo.write(f"{root}/Packages/packages-lock.json", '{"dependencies": {}}\n')


def test_a_unity_project_is_found_by_its_project_settings_and_rooted_above_them(repo: Repo) -> None:
    _unity(repo)
    rows = _rows(repo)
    assert "in Game" in rows["framework.unity.profile"][1]
    assert rows["framework.unity.framework-version"][0] is Verdict.PASSING


def test_a_unity_project_at_the_repo_root_is_rooted_at_the_root(repo: Repo) -> None:
    _unity(repo, ".")
    assert "in ." in _rows(repo)["framework.unity.profile"][1]


def test_unity_tests_outside_the_gate_fail(repo: Repo) -> None:
    _unity(repo)
    repo.write("justfile", "check:\n    true\n\nunity-test:\n    unity -batchmode -runTests -testPlatform EditMode\n")
    repo.write("Game/Assets/Tests/EditMode/Game.Tests.asmdef", '{"references": ["UnityEngine.TestRunner"]}\n')
    assert _rows(repo)["framework.unity.tests"][0] is Verdict.FAILING


def test_unitys_library_cache_is_not_walked_but_a_folder_named_library_elsewhere_is(repo: Repo) -> None:
    _unity(repo, ".")
    repo.write("Library/Bee/Generated.csproj", "<Project/>\n")
    repo.write("Library/PackageCache/ProjectSettings/ProjectVersion.txt", "m_EditorVersion: 6000.3.2f1\n")
    report = run(repo.root, env=repo.env)
    assert not any(r.id.startswith("stack.dotnet") for r in report.rows)
    assert "framework.unity.profile" in {r.id for r in report.rows}
    repo.write("src/Library/Library.csproj", "<Project/>\n")
    assert any(r.id.startswith("stack.dotnet") for r in run(repo.root, env=repo.env).rows)
