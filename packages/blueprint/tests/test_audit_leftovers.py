"""shelf-cni5: a tracked audit baseline or narrative report under docs/blueprint/ is dead weight (ADR 0018)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint.model import Verdict
from blueprint.runner import Row, run

if TYPE_CHECKING:
    from blueprint.testing import Repo

ROW = "gate.no-audit-leftovers"


def _row(repo: Repo) -> Row:
    return {r.id: r for r in run(repo.root, concern="gate", env=repo.env).rows}[ROW]


def test_a_tracked_baseline_fails(repo: Repo) -> None:
    repo.write("docs/blueprint/checkpoints.txt", "gate.ci@1\n")
    repo.commit()
    row = _row(repo)
    assert row.verdict is Verdict.FAILING
    assert "docs/blueprint/checkpoints.txt" in row.evidence
    assert "git rm" in row.remediation


def test_tracked_narrative_reports_fail(repo: Repo) -> None:
    repo.write("docs/blueprint/README.md", "# Blueprint\n\nWritten by `blueprint check --write`\n")
    repo.write("docs/blueprint/gate.md", "# Blueprint: gate (Generic)\n")
    repo.commit()
    row = _row(repo)
    assert row.verdict is Verdict.FAILING
    assert "docs/blueprint/README.md" in row.evidence
    assert "docs/blueprint/gate.md" in row.evidence


def test_the_state_file_and_hand_written_notes_are_not_leftovers(repo: Repo) -> None:
    repo.write("docs/blueprint/blueprint.toml", "")
    repo.write("docs/blueprint/gate-inputs.toml", "")
    repo.write("docs/blueprint/notes.md", "Why we waive the thing.\n")
    repo.commit()
    assert _row(repo).verdict is Verdict.PASSING


def test_a_repo_that_deleted_them_passes(repo: Repo) -> None:
    repo.write("docs/blueprint/checkpoints.txt", "x@1\n")
    repo.commit()
    repo.git("rm", "-q", "docs/blueprint/checkpoints.txt")
    repo.commit()
    assert _row(repo).verdict is Verdict.PASSING


def test_an_untracked_ignored_file_is_not_a_leftover(repo: Repo) -> None:
    repo.write(".gitignore", "docs/blueprint/checkpoints.txt\n")
    repo.write("docs/blueprint/checkpoints.txt", "x@1\n")
    repo.commit()
    assert _row(repo).verdict is Verdict.PASSING
