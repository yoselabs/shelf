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
