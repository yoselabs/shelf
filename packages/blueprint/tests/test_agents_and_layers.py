"""Agent-harness checkpoints, and reports grouped by layer (generic, stack, agent)."""

from __future__ import annotations

import json
import subprocess
from datetime import date
from typing import TYPE_CHECKING

import pytest
from blueprint import report
from blueprint.model import Verdict
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
    repo.write(".claude/settings.json", json.dumps({"env": {"BD_DISABLE_METRICS": "1"}, "hooks": _HOOKS}))
    repo.write(".gitignore", ".claude/worktrees/\n.worktrees/\n")


def test_a_sound_harness_passes_every_agent_checkpoint(repo: Repo) -> None:
    _sound(repo)
    verdicts = _verdicts(repo)
    assert set(verdicts.values()) <= {Verdict.PASSING, Verdict.NOT_APPLICABLE}
    assert verdicts["agents.worktrees-in-sync"] is Verdict.NOT_APPLICABLE  # the main checkout is no linked worktree


def test_a_separate_claude_md_fails(repo: Repo) -> None:
    _sound(repo)
    repo.write("CLAUDE.md", "other rules\n")
    assert _verdicts(repo)["agents.instructions"] is Verdict.FAILING


def test_no_claude_md_passes_and_a_symlink_to_agents_md_fails(repo: Repo) -> None:
    _sound(repo)
    assert _verdicts(repo)["agents.instructions"] is Verdict.PASSING
    repo.root.joinpath("CLAUDE.md").symlink_to("AGENTS.md")
    verdict, evidence, remediation = _evidence(repo, "agents.instructions")
    assert verdict is Verdict.FAILING
    assert "symlink" in evidence
    assert remediation == "git rm CLAUDE.md"


def _evidence(repo: Repo, check_id: str) -> tuple[Verdict, str, str]:
    row = {r.id: r for r in run(repo.root, concern="agents", env=repo.env).rows}[check_id]
    return row.verdict, row.evidence, row.remediation


def test_two_diverging_instruction_files_fail_with_what_differs_and_how_to_merge(repo: Repo) -> None:
    # a2peer: AGENTS.md carried a sync section and shell rules CLAUDE.md lacked, so two agents got two rule sets.
    _sound(repo)
    repo.write("AGENTS.md", "# map\nsync rules\nshell rules\n")
    repo.write("CLAUDE.md", "# map\nbd template\n")
    verdict, evidence, remediation = _evidence(repo, "agents.instructions")
    assert verdict is Verdict.FAILING
    assert "1 line only in CLAUDE.md" in evidence
    assert "2 lines only in AGENTS.md" in evidence
    assert "diff AGENTS.md CLAUDE.md" in remediation
    assert "git rm CLAUDE.md" in remediation


def test_an_identical_copy_is_fixed_by_removing_it(repo: Repo) -> None:
    _sound(repo)
    repo.write("CLAUDE.md", "# map\n")
    verdict, evidence, remediation = _evidence(repo, "agents.instructions")
    assert verdict is Verdict.FAILING
    assert "copy" in evidence
    assert remediation == "git rm CLAUDE.md"


def test_only_a_claude_md_is_renamed_to_agents_md(repo: Repo) -> None:
    repo.write("CLAUDE.md", "# map\n")
    verdict, _, remediation = _evidence(repo, "agents.instructions")
    assert verdict is Verdict.NOT_SET_UP
    assert "git mv CLAUDE.md AGENTS.md" in remediation


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
    repo.write("package.json", "{}")
    paths = {p.name for p in report.write(run(repo.root, env=repo.env), repo.root, date(2026, 10, 10))}
    assert {"README.md", "gate.md", "backlog.md", "stack-node.md", "agents.md"} <= paths
    # Not "Generated ...; do not edit": homelab's generated-file guard fails a file that claims a generator it does not know.
    readme = (repo.root / "docs/blueprint/README.md").read_text()
    assert "Written by `blueprint check --write`" in readme
    assert "Generated by" not in readme


def _worktrees_row(repo: Repo) -> tuple[Verdict, str]:
    row = next(r for r in run(repo.root, concern="agents", env=repo.env).rows if r.id == "agents.worktrees")
    return row.verdict, row.evidence


def test_a_committed_gitignore_missing_on_disk_is_not_a_crash(repo: Repo) -> None:
    # lifesim: git listed client/.gitignore (a stray core.worktree made git answer for another tree) that this tree lacks.
    repo.write(".gitignore", ".claude/worktrees/\n.worktrees/\n")
    repo.write("client/.gitignore", "Library/\n")
    repo.git("add", "-A")
    repo.root.joinpath("client/.gitignore").unlink()
    verdict, evidence = _worktrees_row(repo)
    assert "crashed" not in evidence
    assert verdict is Verdict.PASSING


def test_a_dangling_gitignore_symlink_is_not_a_crash_and_does_not_count(repo: Repo) -> None:
    repo.root.joinpath(".gitignore").symlink_to("nowhere")
    verdict, evidence = _worktrees_row(repo)
    assert "crashed" not in evidence
    assert verdict is Verdict.NOT_SET_UP


def test_a_gitignore_symlinked_to_a_folder_is_not_a_crash(repo: Repo) -> None:
    repo.write("rules/keep", "x")
    repo.root.joinpath(".gitignore").symlink_to("rules")
    verdict, evidence = _worktrees_row(repo)
    assert "crashed" not in evidence
    assert verdict is Verdict.NOT_SET_UP


def test_a_gitignore_symlink_to_a_real_file_does_not_count_because_git_ignores_symlinked_rules(repo: Repo) -> None:
    repo.write("rules.txt", ".claude/worktrees/\n.worktrees/\n")
    repo.root.joinpath(".gitignore").symlink_to("rules.txt")
    assert _worktrees_row(repo)[0] is Verdict.NOT_SET_UP


def test_a_folder_named_gitignore_is_not_a_crash(repo: Repo) -> None:
    repo.write("sub/.gitignore/inner.txt", "x")
    verdict, evidence = _worktrees_row(repo)
    assert "crashed" not in evidence
    assert verdict is Verdict.NOT_SET_UP


def test_a_gitignore_in_a_submodule_and_a_path_with_spaces_are_not_a_crash(repo: Repo, tmp_path: Path) -> None:
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@example.invalid"], ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=vendor, check=True)
    (vendor / ".gitignore").write_text("x\n")
    subprocess.run(["git", "add", "."], cwd=vendor, check=True)
    subprocess.run(["git", "commit", "-qm", "v"], cwd=vendor, check=True)
    repo.write(".gitignore", ".claude/worktrees/\n.worktrees/\n")
    repo.git("-c", "protocol.file.allow=always", "submodule", "add", "-q", str(vendor), "third party/uma lib")
    repo.write("my game/client/.gitignore", "Library/\n")
    verdict, evidence = _worktrees_row(repo)
    assert "crashed" not in evidence
    assert verdict is Verdict.PASSING


def test_an_unreadable_gitignore_is_reported_not_checked_instead_of_raising(repo: Repo) -> None:
    repo.write(".gitignore", ".claude/worktrees/\n.worktrees/\n")
    repo.root.joinpath(".gitignore").chmod(0)
    try:
        verdict, evidence = _worktrees_row(repo)
    finally:
        repo.root.joinpath(".gitignore").chmod(0o644)
    if verdict is Verdict.PASSING:  # running as root: chmod does not stop the read
        return
    assert "crashed" not in evidence
    assert verdict is Verdict.NOT_CHECKED
    assert ".gitignore" in evidence


def test_the_pocock_skills_row_is_gone(repo: Repo) -> None:
    assert "agents.pocock-skills" not in _verdicts(repo)
