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
    repo.write("Makefile", "check:\n\ttrue\nimport:\n\tgodot --headless --import | grep ERROR: ; godot --headless --build-solutions\n")
    assert _rows(repo)["framework.godot.build"][0] is Verdict.FAILING


def test_godot_surface_check_and_in_engine_tests_in_the_gate_pass(repo: Repo) -> None:
    _godot(repo)
    repo.write("tools/check_godot.py", "")
    repo.write("Directory.Packages.props", '<PackageVersion Include="Chickensoft.GoDotTest" Version="2.0.47" />')
    repo.write("src/Game/viewtests/TestEntry.cs", "env.ShouldRunTests")
    repo.write(
        "justfile",
        "check: godot-surface godot-test\n"
        "godot-surface:\n    python3 -I tools/check_godot.py src/Game\n"
        "godot-test:\n    godot --headless --run-tests --quit-on-finish\n",
    )
    rows = _rows(repo)
    assert rows["framework.godot.surface-integrity"][0] is Verdict.PASSING
    assert rows["framework.godot.tests"][0] is Verdict.PASSING


def test_godot_tests_configured_but_outside_the_gate_fail(repo: Repo) -> None:
    _godot(repo)
    repo.write("Directory.Packages.props", '<PackageVersion Include="Chickensoft.GoDotTest" Version="2.0.47" />')
    repo.write("src/Game/viewtests/TestEntry.cs", "env.ShouldRunTests")
    repo.write("justfile", "check:\n    true\ngodot-test:\n    godot --run-tests\n")
    assert _rows(repo)["framework.godot.tests"][0] is Verdict.FAILING


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
    repo.write(
        "tests/test_server.py",
        'async def t(c):\n    r = await c.initialize_result\n    assert r.protocolVersion == "2025-11-25"\n'
        "    assert Client(s) and r.is_error\n",
    )
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


def test_reading_initialize_result_without_asserting_the_protocol_version_is_not_set_up(repo: Repo) -> None:
    # a2kay (shelf-n6i): tests read .instructions and serverInfo.version off initialize_result; none asserted protocolVersion.
    _a2kay_shaped(repo)
    repo.write("tests/test_server.py", "async def t(c):\n    r = await c.initialize_result\n    assert r.instructions\n")
    verdict, evidence = _rows(repo)["framework.mcp.framework-version"]
    assert verdict is Verdict.NOT_SET_UP
    assert "protocolVersion" in evidence


_NO_MCP_IN_CORE = """
[tool.importlinter]
root_packages = ["demo"]
include_external_packages = true

[[tool.importlinter.contracts]]
name = "the core never imports the MCP framework"
type = "forbidden"
source_modules = ["demo.core"]
forbidden_modules = ["fastmcp", "mcp"]
"""


def test_the_mcp_architecture_row_wants_a_contract_keeping_the_framework_out_of_the_core(repo: Repo) -> None:
    # a2kay (shelf-pt0): the row was a blueprint gap; the standard is an import-linter forbidden contract.
    _a2kay_shaped(repo)
    verdict, evidence = _rows(repo)["framework.mcp.architecture"]
    assert verdict is Verdict.NOT_SET_UP
    assert "include_external_packages" in evidence
    repo.write("pyproject.toml", (repo.root / "pyproject.toml").read_text() + _NO_MCP_IN_CORE)
    repo.write("Makefile", "check:\n\tuv run pytest\n\tuv run lint-imports\n")
    assert _rows(repo)["framework.mcp.architecture"][0] is Verdict.PASSING


def _unity_architecture(repo: Repo, root: str = "Game") -> None:
    """Everything the architecture role wants except the per-assembly compiler files."""
    _unity(repo, root)
    repo.write(f"{root}/Assets/Scripts/Core/Lifesim.Core.asmdef", '{"noEngineReferences": true}\n')
    repo.write(f"{root}/Assets/Scripts/Runtime/Lifesim.Runtime.asmdef", '{"references": ["Lifesim.Core"]}\n')
    repo.write("Directory.Build.props", "<GlobalAnalyzerConfigFiles />\n")
    exemptions = "is_global = true\ndotnet_diagnostic.CA1822.severity = none\ndotnet_diagnostic.CA2007.severity = none\n"
    repo.write(f"{root}/Assets/Unity.globalconfig", exemptions)
    repo.write("justfile", "check:\n    dotnet build\n")


_STRICT = "-nullable:enable\n-warnaserror+\n"


def test_unity_strict_compile_needs_a_csc_rsp_next_to_each_project_asmdef_and_names_the_missing_one(repo: Repo) -> None:
    _unity_architecture(repo)
    repo.write("Game/Assets/Scripts/Core/csc.rsp", _STRICT)
    verdict, evidence = _rows(repo)["framework.unity.architecture"]
    assert verdict is Verdict.NOT_SET_UP
    assert "Game/Assets/Scripts/Runtime" in evidence
    assert "Game/Assets/Scripts/Core" not in evidence


def test_unity_strict_compile_passes_with_a_csc_rsp_beside_every_project_asmdef(repo: Repo) -> None:
    _unity_architecture(repo)
    repo.write("Game/Assets/Scripts/Core/csc.rsp", _STRICT)
    repo.write("Game/Assets/Scripts/Runtime/csc.rsp", _STRICT + "-analyzerconfig:Assets/Unity.globalconfig\n")
    assert _rows(repo)["framework.unity.architecture"][0] is Verdict.PASSING


def test_unity_rsp_without_the_strict_flags_does_not_count(repo: Repo) -> None:
    _unity_architecture(repo)
    repo.write("Game/Assets/Scripts/Core/csc.rsp", _STRICT)
    repo.write("Game/Assets/Scripts/Runtime/csc.rsp", "-nullable:enable\n")
    verdict, evidence = _rows(repo)["framework.unity.architecture"]
    assert verdict is Verdict.NOT_SET_UP
    assert "Runtime" in evidence


def test_unity_package_asmdefs_are_not_asked_for_an_rsp(repo: Repo) -> None:
    _unity_architecture(repo)
    repo.write("Game/Assets/Scripts/Core/csc.rsp", _STRICT)
    repo.write("Game/Assets/Scripts/Runtime/csc.rsp", _STRICT)
    repo.write("Game/Packages/com.vendor.x/Runtime/X.asmdef", "{}\n")
    repo.write("Game/Library/PackageCache/y/Y.asmdef", "{}\n")
    assert _rows(repo)["framework.unity.architecture"][0] is Verdict.PASSING


def test_unity_assets_csc_rsp_is_flagged_because_it_hits_packages_too(repo: Repo) -> None:
    _unity_architecture(repo)
    repo.write("Game/Assets/Scripts/Core/csc.rsp", _STRICT)
    repo.write("Game/Assets/Scripts/Runtime/csc.rsp", _STRICT)
    repo.write("Game/Assets/csc.rsp", _STRICT)
    verdict, evidence = _rows(repo)["framework.unity.architecture"]
    assert verdict is not Verdict.PASSING
    assert "Game/Assets/csc.rsp" in evidence
    assert "packages" in evidence
