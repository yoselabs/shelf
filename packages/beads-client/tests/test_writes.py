from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from beads_client import Bd, BdError, NewBead

if TYPE_CHECKING:
    from beads_client.testing import Script

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def argv(script: Script, n: int = 0) -> list[str]:
    return script.calls[n][3:-1]  # between `bd --actor X` and `--json`


def test_create_returns_the_id(bd: Bd, script: Script) -> None:
    script.say(fixture("create.json"))
    new = NewBead("T", priority=1, description="d", labels=("a", "b"), parent="p-1", deps=("x-1",), no_inherit_labels=True)
    assert bd.create(new) == "zz-6q8"
    assert argv(script) == [
        "create",
        "T",
        "--type",
        "task",
        "--description",
        "d",
        "--parent",
        "p-1",
        "--priority",
        "1",
        "--labels",
        "a,b",
        "--deps",
        "x-1",
        "--no-inherit-labels",
    ]


@pytest.mark.parametrize("out", ["", "{}", '{"id": ""}', "[]"])
def test_create_without_an_id_fails_loud(bd: Bd, script: Script, out: str) -> None:
    script.say(out)
    with pytest.raises(BdError) as e:
        bd.create(NewBead("T"))
    assert e.value.kind == "malformed"


LINT = "Error: validation failed: missing required sections for type task: ## Touches, ## Acceptance Criteria"


def test_create_lint_refusal_names_the_sections(bd: Bd, script: Script) -> None:
    script.say(err=LINT, code=1)
    with pytest.raises(BdError) as e:
        bd.create(NewBead("T", description="d"))
    assert (e.value.kind, e.value.missing_sections) == ("lint", ("Touches", "Acceptance Criteria"))


def test_create_with_sections_retries_once_with_filler(bd: Bd, script: Script) -> None:
    script.say(err=LINT, code=1).say(fixture("create.json"))
    assert bd.create_with_sections(NewBead("T", description="d\n\n## Touches\nx"), lambda h: f"({h} unknown)") == "zz-6q8"
    desc = argv(script, 1)[argv(script, 1).index("--description") + 1]
    assert desc == "d\n\n## Touches\nx\n\n## Acceptance Criteria\n(Acceptance Criteria unknown)"


def test_create_with_sections_gives_up_after_one_retry(bd: Bd, script: Script) -> None:
    script.say(err=LINT, code=1).say(err=LINT, code=1)
    with pytest.raises(BdError):
        bd.create_with_sections(NewBead("T", description="d"), lambda h: h)
    assert len(script.calls) == 2


def test_update_argv_and_fences(bd: Bd, script: Script) -> None:
    bd.update(
        "a-1",
        status="open",
        assignee="",
        notes="n",
        set_metadata={"k": "v"},
        unset_metadata=["z"],
        if_assignee="w",
        if_status="in_progress",
    )
    assert argv(script) == [
        "update",
        "a-1",
        "--status",
        "open",
        "--if-assignee",
        "w",
        "--if-status",
        "in_progress",
        "--assignee",
        "",
        "--notes",
        "n",
        "--set-metadata",
        "k=v",
        "--unset-metadata",
        "z",
    ]


def test_if_assignee_empty_means_unassigned(bd: Bd, script: Script) -> None:
    bd.update("a-1", assignee="me", if_assignee="")
    assert "--if-assignee" in argv(script)


def test_exit_13_is_a_typed_precondition_error(bd: Bd, script: Script) -> None:
    script.say(fixture("guard_mismatch.json"), err="Error updating zz-6q8: assignee mismatch", code=13)
    with pytest.raises(BdError) as e:
        bd.update("zz-6q8", notes="x", if_assignee="nobody")
    assert e.value.kind == "precondition"
    assert "assignee mismatch" in e.value.text


def test_claim_outcomes(bd: Bd, script: Script) -> None:
    script.say("[]").say(err="Error updating a-1: issue already claimed by tester", code=1).say(err="boom", code=1)
    assert bd.claim("a-1") is True
    assert argv(script) == ["update", "a-1", "--claim"]
    assert bd.claim("a-1") is False
    with pytest.raises(BdError):
        bd.claim("a-1")


def test_unclaim_outcomes(bd: Bd, script: Script) -> None:
    script.say("[]")
    script.say(err="Error unclaiming zz-zz6: issue claimed by a different actor: held by tester", code=1)
    script.say(err='Error unclaiming zz-zz6: assignee mismatch: held by "tester", expected "nobody"', code=1)
    assert bd.unclaim("a-1", force=True, if_assignee="me") is True
    assert argv(script) == ["unclaim", "a-1", "--force", "--if-assignee", "me"]
    assert bd.unclaim("a-1") is False
    assert bd.unclaim("a-1", if_assignee="nobody") is False


def test_reclaim(bd: Bd, script: Script) -> None:
    script.say(fixture("reclaim.json")).say('{"count": 0, "reclaimed": null}')
    assert bd.reclaim("10m", ids=["zz-6q8"], labels=["l"], any_replica=True) == ["zz-6q8"]
    assert argv(script) == ["reclaim", "--older-than", "10m", "--id", "zz-6q8", "--label", "l", "--any-replica"]
    assert bd.reclaim() == []


def test_heartbeat_raises_when_the_lease_is_gone(bd: Bd, script: Script) -> None:
    script.say('{"id": "a-1", "status": "heartbeat"}')
    bd.heartbeat("a-1")
    script.say('{"error": "heartbeat a-1: issue not claimable: a-1 status open"}', code=1)
    with pytest.raises(BdError) as e:
        bd.heartbeat("a-1")
    assert e.value.kind == "not_claimable"


def test_close_with_fence_updates_first(bd: Bd, script: Script) -> None:
    bd.close("a-1", "done", if_assignee="me")
    assert [argv(script, i) for i in (0, 1)] == [
        ["update", "a-1", "--if-assignee", "me", "--assignee", "me"],
        ["close", "a-1", "--reason", "done"],
    ]


def test_close_stale_fence_writes_nothing(bd: Bd, script: Script) -> None:
    script.say(code=13, err="assignee mismatch")
    with pytest.raises(BdError) as e:
        bd.close("a-1", "done", if_assignee="me")
    assert e.value.kind == "precondition"
    assert len(script.calls) == 1


def test_comment_and_labels(bd: Bd, script: Script) -> None:
    bd.comment("a-1", "hi")
    bd.add_label("a-1", "x", if_assignee="me")
    bd.remove_label("a-1", "x")
    assert [argv(script, i)[0] for i in range(4)] == ["comments", "update", "label", "label"]


def test_provenance(bd: Bd, script: Script) -> None:
    bd.provenance("a-1", "claim", "src", ref="abc", ref_kind="git-sha", payload="{}")
    bd.provenance("a-1", "claim", "src", at="2026-01-01T00:00:00Z")
    assert argv(script, 0) == [
        "provenance",
        "record",
        "--issue",
        "a-1",
        "--kind",
        "claim",
        "--source",
        "src",
        "--ref",
        "abc",
        "--ref-kind",
        "git-sha",
        "--payload",
        "{}",
    ]
    assert argv(script, 1)[-2:] == ["--at", "2026-01-01T00:00:00Z"]
    with pytest.raises(ValueError, match="ref or an at"):
        bd.provenance("a-1", "claim", "src")


def test_sync_rejection_under_exit_zero_is_a_failure(bd: Bd, script: Script) -> None:
    script.say("synced").say(err="! [rejected] main -> main (tip of your current branch is behind)").say(err="conflict", code=2)
    assert bd.sync().ok
    assert bd.sync().code == 1
    assert bd.sync().code == 2
    assert argv(script) == ["sync", "--no-adopt"]


def test_dolt_lock_is_retried_then_succeeds(script: Script) -> None:
    slept: list[float] = []
    bd = Bd("t", exe="bd", run=script, sleep=slept.append)
    script.say(err="embeddeddolt: acquiring lock: busy", code=1).say(err="embeddeddolt: acquiring lock: busy", code=1).say(
        fixture("create.json")
    )
    assert bd.create(NewBead("T")) == "zz-6q8"
    assert len(script.calls) == 3
    assert slept == [0.2, 0.4]


def test_dolt_lock_gives_up(script: Script) -> None:
    bd = Bd("t", exe="bd", run=script, sleep=lambda _s: None, lock_retries=1)
    script.say(err="embeddeddolt: acquiring lock: busy", code=1).say(err="embeddeddolt: acquiring lock: busy", code=1)
    with pytest.raises(BdError):
        bd.create(NewBead("T"))
    assert len(script.calls) == 2


def test_dependencies(bd: Bd, script: Script) -> None:
    script.say(fixture("dep_added.json")).say(fixture("dep_added.json")).say(fixture("dep_removed.json"))
    bd.add_dep("a-1", "a-2")
    bd.add_dep("a-1", "a-2", "related")
    bd.remove_dep("a-1", "a-2")
    assert [argv(script, i) for i in range(3)] == [
        ["dep", "add", "a-1", "a-2"],
        ["dep", "add", "a-1", "a-2", "--type", "related"],
        ["dep", "remove", "a-1", "a-2"],
    ]


def test_dependency_conflict_and_odd_reply(bd: Bd, script: Script) -> None:
    script.say(fixture("dep_exists.json"), code=1).say("{}")
    with pytest.raises(BdError):
        bd.add_dep("a-1", "a-2", "related")
    with pytest.raises(BdError) as e:
        bd.remove_dep("a-1", "a-2")
    assert e.value.kind == "malformed"


@pytest.mark.parametrize(
    "words",
    [
        "embeddeddolt: acquiring lock: resource temporarily unavailable",
        "failed to acquire exclusive lock: timeout",
        "Processes 123 (bd/dolt) may be holding the lock.",
    ],
)
def test_real_lock_strings_are_retried(script: Script, words: str) -> None:
    bd = Bd("t", exe="bd", run=script, sleep=lambda _s: None)
    script.say(err=words, code=1).say(fixture("create.json"))
    assert bd.create(NewBead("T")) == "zz-6q8"
    assert len(script.calls) == 2
