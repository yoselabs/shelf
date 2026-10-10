"""Agent-harness checkpoints, and reports grouped by layer (generic, stack, agent)."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

from blueprint import report, templates
from blueprint.model import Verdict
from blueprint.profile import detect, load_state
from blueprint.runner import run

if TYPE_CHECKING:
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
