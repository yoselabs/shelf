"""Culture templates: installed when missing, never overwritten, the AGENTS.md block kept current."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint import templates
from blueprint.model import Verdict
from blueprint.profile import detect, load_state
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo


def _install(repo: Repo) -> list[str]:
    return templates.install(repo.root, detect(repo.root, load_state(repo.root)))


def _verdicts(repo: Repo) -> dict[str, Verdict]:
    return {r.id: r.verdict for r in run(repo.root, concern="agents", env=repo.env).rows}


def test_a_dotnet_godot_beads_repo_gets_every_file_it_needs(repo: Repo) -> None:
    repo.write(".beads/config.yaml", "")
    repo.write("App.sln", "")
    repo.write("src/Game/project.godot", "")
    names = {p.removeprefix("docs/agents/") for p in _install(repo) if p.startswith("docs/")}
    assert names == {f"{n}.md" for n in (*templates.ALWAYS, "issue-tracker", "dotnet", "godot")}
    block = (repo.root / "AGENTS.md").read_text()
    assert "docs/agents/dotnet.md" in block
    assert "docs/agents/godot.md" in block


def test_a_unity_project_gets_the_unity_conventions_file(repo: Repo) -> None:
    repo.write("Game/ProjectSettings/ProjectVersion.txt", "m_EditorVersion: 6000.3.2f1\n")
    assert "docs/agents/unity.md" in _install(repo)


def test_an_existing_file_is_never_overwritten_and_a_second_run_changes_nothing(repo: Repo) -> None:
    repo.write("docs/agents/constitution.md", "ours\n")
    _install(repo)
    assert (repo.root / "docs/agents/constitution.md").read_text() == "ours\n"
    assert _install(repo) == []


def test_the_block_is_replaced_between_its_markers_and_the_rest_kept(repo: Repo) -> None:
    repo.write("AGENTS.md", f"# Mine\n\nkeep this\n\n{templates.BEGIN}\nstale\n{templates.END}\n\nand this\n")
    _install(repo)
    text = (repo.root / "AGENTS.md").read_text()
    assert "keep this" in text
    assert "and this" in text
    assert "stale" not in text
    assert text.count(templates.BEGIN) == 1


def test_missing_files_are_not_set_up_and_unfilled_placeholders_fail(repo: Repo) -> None:
    assert _verdicts(repo)["agents.culture-files"] is Verdict.NOT_SET_UP
    _install(repo)
    assert _verdicts(repo)["agents.culture-files"] is Verdict.FAILING
    for path in (repo.root / "docs/agents").glob("*.md"):
        path.write_text(templates.PLACEHOLDER.sub("filled", path.read_text()))
    assert _verdicts(repo)["agents.culture-files"] is Verdict.PASSING


def test_the_python_template_states_no_tool_of_the_shelfs_own(repo: Repo) -> None:
    # a2kay uses coverage.py, import-linter, make test-fast and docs/glossary.md; the template taught every
    # agent the shelf's pytest-cov, "no architecture tool", make test-affected and CONTEXT.md instead.
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    _install(repo)
    text = (repo.root / "docs/agents/python.md").read_text()
    for shelf_only in ("pytest-cov", "test-affected", "CONTEXT.md", "import-linter", "none chosen", "pyrefly"):
        assert shelf_only not in text
    for role in ("toolchain", "formatter", "linter", "types", "spelling", "dependencies", "tests", "coverage", "architecture", "hooks"):
        assert f"{{{{{role}_tool}}}}" in text
        assert f"{{{{{role}_run}}}}" in text
    assert "{{glossary_file}}" in text
    assert _verdicts(repo)["agents.culture-files"] is Verdict.FAILING


def test_a_stale_block_fails_and_a_fresh_one_passes(repo: Repo) -> None:
    _install(repo)
    assert _verdicts(repo)["agents.managed-block"] is Verdict.PASSING
    repo.write("App.sln", "")
    assert _verdicts(repo)["agents.managed-block"] is Verdict.FAILING


def test_a_gate_that_never_runs_blueprint_is_not_set_up(repo: Repo) -> None:
    repo.write("Makefile", "check: lint\nlint:\n\ttrue\n")
    rows = {r.id: r.verdict for r in run(repo.root, concern="gate", env=repo.env).rows}
    assert rows["gate.runs-blueprint"] is Verdict.NOT_SET_UP
    repo.write("Makefile", "check: blueprint\nblueprint:\n\tpython3 -m blueprint check --repo . --gate\n")
    rows = {r.id: r.verdict for r in run(repo.root, concern="gate", env=repo.env).rows}
    assert rows["gate.runs-blueprint"] is Verdict.PASSING


def test_an_mcp_server_gets_its_conventions_file_and_a_block_row(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "demo"\nversion = "0"\ndependencies = ["fastmcp>=3.4,<4"]\n')
    repo.write("src/demo/server.py", "from fastmcp import FastMCP\nmcp = FastMCP('d')\n")
    assert "docs/agents/mcp.md" in _install(repo)
    assert "docs/agents/mcp.md" in (repo.root / "AGENTS.md").read_text()
