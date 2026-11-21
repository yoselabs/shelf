"""gate.recipe-calls: a recipe's call of blueprint names flags that exist and runs the pinned engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo


def _calls(repo: Repo, body: str) -> tuple[Verdict, str]:
    repo.write("justfile", f"check:\n    true\n\nblueprint:\n    {body}\n")
    rows = {r.id: r for r in run(repo.root, concern="gate", env=repo.env).rows}
    return rows["gate.recipe-calls"].verdict, rows["gate.recipe-calls"].evidence


@pytest.mark.parametrize(
    "body",
    [
        "uv run blueprint check --repo . --brief",
        "uv run blueprint gate test --repo . --pytest-args=''",
        "python3 -m blueprint check --repo . --json",
        "uv run blueprint gate preset",
        "echo nothing to see",
    ],
)
def test_calls_with_flags_that_exist_pass(repo: Repo, body: str) -> None:
    assert _calls(repo, body)[0] is Verdict.PASSING


def test_a_flag_blueprint_never_had_fails_naming_recipe_command_and_flag(repo: Repo) -> None:
    verdict, evidence = _calls(repo, "uv run blueprint check --repo . --nonsense")
    assert verdict is Verdict.FAILING
    assert "blueprint" in evidence
    assert "`blueprint check`" in evidence
    assert "--nonsense" in evidence


def test_the_removed_gate_flag_fails_the_recipe_that_still_calls_it(repo: Repo) -> None:
    # homelab, 2026-11-21: `check --gate` was removed for `--brief`; its pre-push gate found out at the push, not at the audit.
    verdict, evidence = _calls(repo, "python3 -m blueprint check --repo . --gate")
    assert verdict is Verdict.FAILING
    assert "--gate" in evidence


def test_a_flag_on_the_wrong_command_fails(repo: Repo) -> None:
    verdict, evidence = _calls(repo, "uv run blueprint gate guard --reference x")
    assert verdict is Verdict.FAILING
    assert "`blueprint gate guard`" in evidence


@pytest.mark.parametrize(
    "body",
    [
        "PYTHONPATH=$HOME/Workspaces/shelf/packages/blueprint/src python3 -m blueprint check --repo . --brief",
        "python3 ~/Workspaces/shelf/packages/blueprint/src/blueprint/__main__.py check",
        "uv run blueprint gate preset --reference ~/Workspaces/shelf/preset.toml",
    ],
)
def test_the_engine_run_from_a_shelf_clone_fails(repo: Repo, body: str) -> None:
    verdict, evidence = _calls(repo, body)
    assert verdict is Verdict.FAILING
    assert "shelf clone" in evidence
