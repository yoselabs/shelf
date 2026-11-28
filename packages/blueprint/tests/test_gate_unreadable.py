"""A Makefile-only repo's gate rows say the gate is unreadable; they never claim `not applicable` (the 0.17 corpus diff: 27 repos)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

READS_THE_GATE = [
    "gate.step-inputs",
    "gate.wide-inputs-have-a-reason",
    "gate.runs-blueprint",
    "gate.guards-have-red-tests",
    "gate.checkers-wired",
    "gate.recipe-calls",
]


@pytest.mark.parametrize("row", READS_THE_GATE)
def test_a_makefile_only_repo_is_not_set_up_because_the_gate_is_unreadable(repo: Repo, row: str) -> None:
    repo.write("Makefile", "check:\n\ttrue\n")
    repo.commit()
    got = {r.id: r for r in run(repo.root, concern="gate", env=repo.env).rows}[row]
    assert got.verdict is Verdict.NOT_SET_UP
    assert "not set up because the gate is unreadable" in got.evidence


@pytest.mark.parametrize("row", READS_THE_GATE)
def test_a_repo_with_no_gate_at_all_keeps_its_rows_not_applicable(repo: Repo, row: str) -> None:
    got = {r.id: r for r in run(repo.root, concern="gate", env=repo.env).rows}[row]
    assert got.verdict is not Verdict.NOT_SET_UP or "unreadable" not in got.evidence
