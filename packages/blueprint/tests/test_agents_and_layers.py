"""Agent-harness checkpoints, and reports grouped by layer (generic, stack, agent)."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

import pytest
from blueprint import report, templates
from blueprint.model import Verdict
from blueprint.profile import detect, load_state
from blueprint.runner import run

if TYPE_CHECKING:
    from pathlib import Path

    from blueprint.testing import Repo

_HOOKS = {
    "SessionStart": [{"hooks": [{"type": "command", "command": "bd prime --hook-json"}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "bd list --status in_progress --json"}]}],
}


def _verdicts(repo: Repo) -> dict[str, Verdict]:
    return {r.id: r.verdict for r in run(repo.root, concern="agents", env=repo.env).rows}


def _sound(repo: Repo) -> None:
    repo.write(".beads/config.yaml", "")
    repo.write("AGENTS.md", "# map\n")
    repo.root.joinpath("CLAUDE.md").symlink_to("AGENTS.md")
    repo.write(".claude/settings.json", json.dumps({"env": {"BD_DISABLE_METRICS": "1"}, "hooks": _HOOKS}))
    repo.write(".gitignore", ".claude/worktrees/\n.worktrees/\n")


def test_a_sound_harness_passes_every_agent_checkpoint(repo: Repo) -> None:
    _sound(repo)
    templates.install(repo.root, detect(repo.root, load_state(repo.root)))
    for path in (repo.root / "docs/agents").glob("*.md"):
        path.write_text(templates.PLACEHOLDER.sub("filled", path.read_text()))
    assert set(_verdicts(repo).values()) == {Verdict.PASSING}


def test_a_separate_claude_md_fails(repo: Repo) -> None:
    _sound(repo)
    repo.root.joinpath("CLAUDE.md").unlink()
    repo.write("CLAUDE.md", "other rules\n")
    assert _verdicts(repo)["agents.instructions"] is Verdict.FAILING


def _evidence(repo: Repo, check_id: str) -> tuple[Verdict, str, str]:
    row = {r.id: r for r in run(repo.root, concern="agents", env=repo.env).rows}[check_id]
    return row.verdict, row.evidence, row.remediation


def test_two_diverging_instruction_files_fail_with_what_differs_and_how_to_merge(repo: Repo) -> None:
    # a2peer: AGENTS.md carried a sync section and shell rules CLAUDE.md lacked, so two agents got two rule sets.
    _sound(repo)
    repo.root.joinpath("CLAUDE.md").unlink()
    repo.write("AGENTS.md", "# map\nsync rules\nshell rules\n")
    repo.write("CLAUDE.md", "# map\nbd template\n")
    verdict, evidence, remediation = _evidence(repo, "agents.instructions")
    assert verdict is Verdict.FAILING
    assert "1 line only in CLAUDE.md" in evidence
    assert "2 lines only in AGENTS.md" in evidence
    assert "diff AGENTS.md CLAUDE.md" in remediation
    assert "ln -sf AGENTS.md CLAUDE.md" in remediation


def test_an_identical_copy_is_fixed_by_the_link_alone(repo: Repo) -> None:
    _sound(repo)
    repo.root.joinpath("CLAUDE.md").unlink()
    repo.write("CLAUDE.md", "# map\n")
    verdict, evidence, remediation = _evidence(repo, "agents.instructions")
    assert verdict is Verdict.FAILING
    assert "copy" in evidence
    assert remediation == "ln -sf AGENTS.md CLAUDE.md"


def test_only_a_claude_md_is_renamed_to_agents_md(repo: Repo) -> None:
    repo.write("CLAUDE.md", "# map\n")
    verdict, _, remediation = _evidence(repo, "agents.instructions")
    assert verdict is Verdict.NOT_SET_UP
    assert "mv CLAUDE.md AGENTS.md" in remediation


_BD_TEMPLATE = "# Project\n\n## Build & Test\n\n{build}\n\n## Architecture Overview\n\n{arch}\n\n## Conventions & Patterns\n\n{conv}\n"


def _filled_harness(repo: Repo) -> None:
    _sound(repo)
    templates.install(repo.root, detect(repo.root, load_state(repo.root)))
    for path in (repo.root / "docs/agents").glob("*.md"):
        path.write_text(templates.PLACEHOLDER.sub("filled", path.read_text()))


@pytest.mark.parametrize("mark", ["*", "_"])
def test_bd_template_placeholders_left_in_claude_md_fail_and_pass_once_replaced(repo: Repo, mark: str) -> None:
    # a2peer: `bd init` wrote these three lines and nobody replaced them, so agents had no build or test command.
    _filled_harness(repo)
    repo.root.joinpath("CLAUDE.md").unlink()
    repo.write(
        "CLAUDE.md",
        _BD_TEMPLATE.format(
            build=f"{mark}Add your build and test commands here{mark}",
            arch=f"{mark}Add a brief overview of your project architecture{mark}",
            conv=f"{mark}Add your project-specific conventions here{mark}",
        ),
    )
    verdict, evidence, _ = _evidence(repo, "agents.culture-files")
    assert verdict is Verdict.FAILING
    assert "CLAUDE.md" in evidence
    assert "3 template placeholder" in evidence
    repo.write("CLAUDE.md", _BD_TEMPLATE.format(build="`make check`", arch="a package per concern", conv="tests first"))
    assert _evidence(repo, "agents.culture-files")[0] is Verdict.PASSING


def test_a_mustache_placeholder_in_agents_md_fails(repo: Repo) -> None:
    _filled_harness(repo)
    repo.write("AGENTS.md", "# {{project_name}}\n")
    verdict, evidence, _ = _evidence(repo, "agents.culture-files")
    assert verdict is Verdict.FAILING
    assert "AGENTS.md" in evidence


def test_a_symlinked_claude_md_is_read_once(repo: Repo) -> None:
    _filled_harness(repo)
    repo.write("AGENTS.md", "# map\n_Add your build and test commands here_\n")
    _, evidence, _ = _evidence(repo, "agents.culture-files")
    assert "1 template placeholder" in evidence


def test_worktree_folders_not_ignored_is_not_set_up(repo: Repo) -> None:
    _sound(repo)
    repo.write(".gitignore", ".claude/worktrees/\n")
    assert _verdicts(repo)["agents.worktrees"] is Verdict.NOT_SET_UP


@pytest.mark.parametrize("where", [".git/info/exclude", "global"])
def test_worktree_folders_ignored_only_clone_locally_is_not_set_up(repo: Repo, tmp_path: Path, where: str) -> None:
    # a2kay: the rule sat in .git/info/exclude, so the host passed and a fresh clone (the test container) failed.
    _sound(repo)
    repo.root.joinpath(".gitignore").unlink()
    if where == "global":
        excludes = tmp_path / "global-ignore"
        excludes.write_text(".claude/worktrees/\n.worktrees/\n")
        repo.git("config", "core.excludesFile", str(excludes))
    else:
        repo.write(".git/info/exclude", "**/.claude/worktrees/\n.worktrees/\n")
    verdicts = _verdicts(repo)
    assert verdicts["agents.worktrees"] is Verdict.NOT_SET_UP


def test_a_nested_gitignore_in_the_repo_counts(repo: Repo) -> None:
    _sound(repo)
    repo.write(".claude/.gitignore", "worktrees/\n")
    repo.write(".gitignore", ".worktrees/\n")
    assert _verdicts(repo)["agents.worktrees"] is Verdict.PASSING


def test_metrics_left_on_is_not_set_up(repo: Repo) -> None:
    _sound(repo)
    repo.write(".claude/settings.json", json.dumps({"hooks": _HOOKS}))
    assert _verdicts(repo)["agents.bd-metrics-off"] is Verdict.NOT_SET_UP


def test_a_missing_session_hook_is_not_set_up(repo: Repo) -> None:
    _sound(repo)
    repo.write(".claude/settings.json", json.dumps({"env": {"BD_DISABLE_METRICS": "1"}, "hooks": {"SessionStart": _HOOKS["SessionStart"]}}))
    assert _verdicts(repo)["agents.session-hooks"] is Verdict.NOT_SET_UP


def test_rows_carry_their_layer_and_the_summary_groups_by_it(repo: Repo) -> None:
    _sound(repo)
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    result = run(repo.root, env=repo.env)
    layers = {r.concern: r.layer for r in result.rows}
    assert layers["gate"] == "generic"
    assert layers["stack/python"] == "stack"
    assert layers["agents"] == "agent"
    text = report.summary(result)
    assert text.index("Generic") < text.index("Stack-specific") < text.index("Agent harness")


def test_write_adds_a_summary_index_and_one_file_per_concern(repo: Repo) -> None:
    _sound(repo)
    repo.write("go.mod", "module x\n")
    paths = {p.name for p in report.write(run(repo.root, env=repo.env), repo.root, date(2026, 10, 10))}
    assert {"README.md", "gate.md", "backlog.md", "stack-go.md", "agents.md"} <= paths
