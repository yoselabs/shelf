"""Backlog checkpoints, against a fake `bd`: each seen passing and failing on a planted violation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from blueprint.concerns.backlog import STRICT
from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo


def _beads(repo: Repo, *, config: dict[str, str] | None = None, lint_exit: int = 0) -> None:
    repo.write(".beads/config.yaml", "")
    repo.write(".claude/settings.json", json.dumps({"env": {"BD_DISABLE_METRICS": "1"}}))
    repo.fake_bd(STRICT if config is None else config, lint_exit=lint_exit, lint_out="shelf-1 missing acceptance criteria")


def _verdicts(repo: Repo) -> dict[str, Verdict]:
    return {r.id: r.verdict for r in run(repo.root, concern="backlog", audit=True, env=repo.env).rows}


def test_a_strict_quiet_beads_repo_passes_every_backlog_checkpoint(repo: Repo) -> None:
    _beads(repo)
    assert set(_verdicts(repo).values()) == {Verdict.PASSING}


def test_no_beads_means_the_tracker_is_not_set_up_and_beads_checks_do_not_run(repo: Repo) -> None:
    assert _verdicts(repo) == {"backlog.tracker": Verdict.NOT_SET_UP}


@pytest.mark.parametrize(("key", "weak"), [("validation.on-create", "warn"), ("export.auto", "true"), ("no-git-ops", "false")])
def test_a_weakened_setting_fails_strict_config(repo: Repo, key: str, weak: str) -> None:
    _beads(repo, config={**STRICT, key: weak})
    assert _verdicts(repo)["backlog.strict-config"] is Verdict.FAILING


def test_a_setting_from_the_environment_fails_strict_config(repo: Repo) -> None:
    _beads(repo)
    shown = json.loads((repo.bin_dir / "bd.json").read_text())
    shown[0]["source"] = "env"
    (repo.bin_dir / "bd.json").write_text(json.dumps(shown))
    assert _verdicts(repo)["backlog.strict-config"] is Verdict.FAILING


def test_metrics_left_on_is_not_set_up(repo: Repo) -> None:
    _beads(repo)
    repo.write(".claude/settings.json", "{}")
    assert _verdicts(repo)["backlog.metrics-off"] is Verdict.NOT_SET_UP


def test_a_tracked_jsonl_export_fails(repo: Repo) -> None:
    _beads(repo)
    repo.write(".beads/issues.jsonl", "{}\n")
    repo.commit()
    assert _verdicts(repo)["backlog.no-tracked-export"] is Verdict.FAILING


@pytest.mark.parametrize("plant", ["local-file", "session-env"])
def test_a_local_override_fails(repo: Repo, plant: str) -> None:
    _beads(repo)
    if plant == "local-file":
        repo.write(".beads/config.local.yaml", "validation:\n  on-create: none\n")
    else:
        repo.write(".claude/settings.json", json.dumps({"env": {"BD_DISABLE_METRICS": "1", "BD_VALIDATION_ON_CREATE": "none"}}))
    assert _verdicts(repo)["backlog.no-local-override"] is Verdict.FAILING


def test_a_bead_failing_lint_fails(repo: Repo) -> None:
    _beads(repo, lint_exit=1)
    assert _verdicts(repo)["backlog.lint"] is Verdict.FAILING


def test_a_second_backlog_file_fails(repo: Repo) -> None:
    _beads(repo)
    repo.write("TODO.md", "- [ ] something\n")
    assert _verdicts(repo)["backlog.no-tracker-file"] is Verdict.FAILING


def test_bd_missing_is_not_checked_never_a_pass(repo: Repo) -> None:
    _beads(repo)
    repo.env["PATH"] = "/nonexistent"
    verdicts = _verdicts(repo)
    assert verdicts["backlog.strict-config"] is Verdict.NOT_CHECKED
    assert verdicts["backlog.lint"] is Verdict.NOT_CHECKED


def test_the_gate_run_leaves_out_what_needs_bds_database(repo: Repo) -> None:
    _beads(repo)
    ids = {r.id for r in run(repo.root, concern="backlog", env=repo.env).rows}
    assert "backlog.strict-config" not in ids
    assert "backlog.lint" not in ids
    assert "backlog.metrics-off" in ids
