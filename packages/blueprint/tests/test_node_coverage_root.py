"""The node rows judge the node project's folder: a project in ui/ keeps its vitest config and floor there (a2kay, 2026-11-22)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_PROJECT = {
    "scripts": {"test": "vitest run --coverage"},
    "devDependencies": {"vitest": "1.0.0", "@vitest/coverage-v8": "1.0.0"},
}
_FLOOR = "export default { test: { coverage: { thresholds: { lines: 59, branches: 48 } } } }\n"
_NO_FLOOR = "export default { test: { coverage: { reporter: ['text'] } } }\n"


def _coverage(repo: Repo) -> tuple[Verdict, str]:
    rows = {r.id: (r.verdict, r.evidence) for r in run(repo.root, concern="stack", env=repo.env).rows}
    return rows["stack.node.coverage"]


def _project(repo: Repo, *, folder: str, config: str, text: str, gate: str) -> None:
    repo.write(f"{folder}package.json", json.dumps(_PROJECT))
    repo.write(f"{folder}{config}", text)
    repo.write("justfile", f"check:\n\t{gate}\n")


@pytest.mark.parametrize("config", ["vitest.config.js", "vitest.config.mjs", "vitest.config.ts", "vitest.config.mts"])
def test_a_floor_in_the_project_folder_passes(repo: Repo, config: str) -> None:
    _project(repo, folder="ui/", config=config, text=_FLOOR, gate="cd ui && vitest run --coverage")
    verdict, evidence = _coverage(repo)
    assert verdict is Verdict.PASSING, evidence


def test_a_project_at_the_repo_root_still_passes(repo: Repo) -> None:
    _project(repo, folder="", config="vitest.config.js", text=_FLOOR, gate="vitest run --coverage")
    verdict, evidence = _coverage(repo)
    assert verdict is Verdict.PASSING, evidence


def test_a_config_with_coverage_but_no_thresholds_does_not_pass(repo: Repo) -> None:
    _project(repo, folder="ui/", config="vitest.config.js", text=_NO_FLOOR, gate="cd ui && vitest run --coverage")
    verdict, _ = _coverage(repo)
    assert verdict is not Verdict.PASSING


def test_a_floor_at_the_repo_root_does_not_stand_in_for_the_project_folder(repo: Repo) -> None:
    _project(repo, folder="ui/", config="vitest.config.js", text=_NO_FLOOR, gate="cd ui && vitest run --coverage")
    repo.write("vitest.config.js", _FLOOR)
    verdict, _ = _coverage(repo)
    assert verdict is not Verdict.PASSING
