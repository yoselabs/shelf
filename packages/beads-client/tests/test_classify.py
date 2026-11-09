"""The words that classify a bd failure, pinned against output recorded from bd 1.3.1."""

from __future__ import annotations

import pytest

from beads_client import BdRun
from beads_client.classify import error_of


@pytest.mark.parametrize(
    ("run", "kind"),
    [
        (BdRun(1, "", "Issue tl-x not found"), "not_found"),
        (BdRun(1, '{"error": "no issues found matching the provided IDs"}', ""), "not_found"),
        (BdRun(1, "", "Error updating zz-zz6: issue already claimed by tester"), "not_claimable"),
        (BdRun(1, "", "issue claimed by a different actor: zz-zz6 is held by tester"), "not_claimable"),
        (BdRun(1, '{"error": "heartbeat a: issue not claimable: a status open"}', ""), "not_claimable"),
        (BdRun(13, "", "assignee mismatch"), "precondition"),
        (BdRun(1, "", 'assignee mismatch: zz is held by "t", expected "n"'), "precondition"),
        (BdRun(1, "", "validation failed: missing required sections for type task: ## Touches"), "lint"),
        (BdRun(1, "", "something else"), "other"),
        (BdRun(1, "", "database not found"), "other"),
        (BdRun(1, "", "Issue tl-x not found\n" + " " * 500 + "database not found"), "other"),
        (BdRun(1, '{"error":"table not found"}', ""), "other"),
        (BdRun(1, "", "no issue table is available: database unavailable"), "other"),
        (BdRun(1, '{"error":"no issues found matching the provided IDs"}', "database not found"), "other"),
        (BdRun(1, "", "Issue tl-x not found\nError: connection refused"), "other"),
        (BdRun(1, '{"error":"backend unavailable"}', "Issue tl-x not found"), "other"),
        (BdRun(127, "", "bd: no such file"), "missing_binary"),
        (BdRun(124, "", "bd: no answer in 3s"), "timeout"),
    ],
)
def test_kind(run: BdRun, kind: str) -> None:
    assert error_of(run).kind == kind
