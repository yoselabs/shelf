"""Hook anti-patterns (design D6): each checkpoint has a config that fails it and one that passes, and a finding names the line."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_GOOD = """\
repos:
- repo: local
  hooks:
  - id: ruff
    name: ruff
    entry: ruff check
    language: system
    stages: [pre-commit]
  - id: gate
    name: just check
    entry: uv run python -m any_gate pre-push --gate check -- uv run just check
    language: system
    always_run: true
    pass_filenames: false
    stages: [pre-push]
"""


def _hook(hook_id: str, entry: str, *, stages: str | None = "[pre-commit]", extra: str = "") -> str:
    lines = f"  - id: {hook_id}\n    name: {hook_id}\n    entry: {entry}\n    language: system\n"
    return lines + (f"    stages: {stages}\n" if stages else "") + extra


def _rows(repo: Repo, config: str | None) -> dict[str, tuple[Verdict, str]]:
    repo.write("README.md", "x\n")
    if config is not None:
        repo.write(".pre-commit-config.yaml", config)
    repo.commit()
    return {r.id: (r.verdict, r.evidence) for r in run(repo.root, concern="hooks", env=repo.env).rows}


def test_a_lean_config_passes_every_hook_checkpoint(repo: Repo) -> None:
    rows = _rows(repo, _GOOD)
    assert {v for v, _ in rows.values()} == {Verdict.PASSING}
    assert len(rows) == 5


def test_a_repo_without_a_hook_config_has_nothing_to_judge(repo: Repo) -> None:
    rows = _rows(repo, None)
    assert {v for v, _ in rows.values()} == {Verdict.NOT_APPLICABLE}


@pytest.mark.parametrize("entry", ["uv run pytest -q", "just check", "make test", "dotnet test", "npm test", "cargo test", "go test ./..."])
def test_tests_at_commit_fail_and_name_the_line(repo: Repo, entry: str) -> None:
    verdict, evidence = _rows(repo, _GOOD + _hook("slow", entry))["hooks.no-tests-at-commit"]
    assert verdict is Verdict.FAILING
    assert "slow" in evidence
    assert "line 16" in evidence


def test_a_hook_without_stages_runs_at_commit(repo: Repo) -> None:
    verdict, _ = _rows(repo, _GOOD + _hook("slow", "uv run pytest", stages=None))["hooks.no-tests-at-commit"]
    assert verdict is Verdict.FAILING


def test_tests_in_pre_push_are_fine(repo: Repo) -> None:
    config = _GOOD + _hook("slow", "uv run pytest", stages="[pre-push]")
    assert _rows(repo, config)["hooks.no-tests-at-commit"][0] is Verdict.PASSING


def test_a_pre_push_hook_that_is_not_the_gate_fails(repo: Repo) -> None:
    verdict, evidence = _rows(repo, _GOOD + _hook("lint-all", "ruff check .", stages="[pre-push]"))["hooks.pre-push-is-the-gate"]
    assert verdict is Verdict.FAILING
    assert "lint-all" in evidence


def test_bds_pre_push_hooks_are_not_a_second_gate(repo: Repo) -> None:
    config = _GOOD + _hook("bd-pre-push", "bd hooks run pre-push", stages="[pre-push]") + _hook("bd-dolt-push", "bd dolt push", stages="[pre-push]")
    assert _rows(repo, config)["hooks.pre-push-is-the-gate"][0] is Verdict.PASSING


@pytest.mark.parametrize(
    "entry",
    ["ruff check || true", "sh -c 'ruff check; exit 0'", "ruff check || :", "sh -c 'ruff check || exit 0'"],
)
def test_a_hook_that_always_exits_zero_fails(repo: Repo, entry: str) -> None:
    verdict, evidence = _rows(repo, _GOOD + _hook("soft", entry))["hooks.fail-closed"]
    assert verdict is Verdict.FAILING
    assert "soft" in evidence


def test_bds_dolt_push_that_exits_zero_on_success_is_fail_closed(repo: Repo) -> None:
    entry = "sh -c 'bd dolt push && exit 0; echo FAILED >&2; test -n \"${OPTIONAL:-}\"'"
    assert _rows(repo, _GOOD + _hook("bd-dolt-push", entry, stages="[pre-push]"))["hooks.fail-closed"][0] is Verdict.PASSING


@pytest.mark.parametrize("path", ["$SHELF_HOME/tools/guard.py", "../shelf/tools/guard.py", "~/Workspaces/shelf/tools/guard.py", "$HOME/Workspaces/shelf/x"])
def test_a_hook_resolved_through_a_shelf_clone_fails(repo: Repo, path: str) -> None:
    verdict, evidence = _rows(repo, _GOOD + _hook("guard", f"python3 {path}"))["hooks.no-clone-path"]
    assert verdict is Verdict.FAILING
    assert "guard" in evidence


def test_a_hook_through_a_pinned_dependency_passes_the_clone_check(repo: Repo) -> None:
    assert _rows(repo, _GOOD + _hook("guard", "uv run blueprint guard"))["hooks.no-clone-path"][0] is Verdict.PASSING


def test_a_gate_hook_that_can_be_skipped_fails(repo: Repo) -> None:
    config = _GOOD.replace("    always_run: true\n", "")
    verdict, evidence = _rows(repo, config)["hooks.gate-always-runs"]
    assert verdict is Verdict.FAILING
    assert "always_run" in evidence


def test_a_gate_hook_filtered_by_files_fails(repo: Repo) -> None:
    config = _GOOD.replace("    always_run: true\n", "    always_run: true\n    files: ^src/\n")
    assert _rows(repo, config)["hooks.gate-always-runs"][0] is Verdict.FAILING


def test_a_repo_with_no_gate_hook_leaves_it_to_the_recipe_checkpoint(repo: Repo) -> None:
    verdict, _ = _rows(repo, _hook("ruff", "ruff check"))["hooks.gate-always-runs"]
    assert verdict is Verdict.NOT_APPLICABLE
