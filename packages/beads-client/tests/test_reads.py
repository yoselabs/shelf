from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from beads_client import Bd, BdError

if TYPE_CHECKING:
    from beads_client.testing import Script

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_show_parses_recorded_bd_json(bd: Bd, script: Script) -> None:
    script.say(fixture("show.json"))
    bead = bd.show("zz-6q8")
    assert bead is not None
    assert (bead.id, bead.title, bead.status, bead.priority) == ("zz-6q8", "T one", "open", 2)
    assert script.calls == [["bd", "--actor", "tester", "show", "zz-6q8", "--json"]]


def test_show_unknown_bead_is_none(bd: Bd, script: Script) -> None:
    script.say(fixture("not_found.json"), err="Issue zz-x not found", code=1)
    assert bd.show("zz-x") is None


def test_show_empty_list_reply_is_none(bd: Bd, script: Script) -> None:
    script.say("[]")
    assert bd.show("zz-x") is None


@pytest.mark.parametrize("out", ["", "not json", '{"no": "id"}', '[{"id": ""}]', "[1]"])
def test_show_malformed_reply_raises_never_absence(bd: Bd, script: Script, out: str) -> None:
    script.say(out)
    with pytest.raises(BdError) as e:
        bd.show("zz-1")
    assert e.value.kind == "malformed"


def test_show_unreachable_bd_raises(bd: Bd, script: Script) -> None:
    script.say(err="Error: database busy", code=1)
    with pytest.raises(BdError) as e:
        bd.show("zz-1")
    assert e.value.kind == "other"


def test_show_missing_binary(bd: Bd, script: Script) -> None:
    script.say(err="bd: No such file", code=127)
    with pytest.raises(BdError) as e:
        bd.show("zz-1")
    assert e.value.kind == "missing_binary"


def test_timeout(bd: Bd, script: Script) -> None:
    script.say(err="bd: no answer in 5s", code=124)
    with pytest.raises(BdError) as e:
        bd.find()
    assert e.value.kind == "timeout"


def test_list_and_ready_empty_output_is_no_rows(bd: Bd, script: Script) -> None:
    script.say("").say("  \n")
    assert bd.find() == []
    assert bd.ready() == []


def test_find_argv(bd: Bd, script: Script) -> None:
    script.say(f"[{fixture('show.json').strip()[1:-1]}]")
    assert [b.id for b in bd.find(status="open", label="shelf", include_closed=True)] == ["zz-6q8"]
    assert script.calls[0][3:] == ["list", "-n", "0", "--all", "--status", "open", "--label", "shelf", "--json"]


def test_list_dependency_shapes_are_normalised(bd: Bd, script: Script) -> None:
    script.say(
        '[{"id": "a-1", "dependencies": [{"depends_on_id": "a-0", "type": "blocks"}, {"id": "a-9", "dependency_type": "parent-child"}]}]'
    )
    deps = bd.find()[0].dependencies
    assert [(d.id, d.type) for d in deps] == [("a-0", "blocks"), ("a-9", "parent-child")]


def test_comments(bd: Bd, script: Script) -> None:
    script.say(fixture("comments.json"))
    assert [(c.author, c.text) for c in bd.comments("zz-6q8")] == [("tester", "hi")]


def test_comments_malformed(bd: Bd, script: Script) -> None:
    script.say('{"oops": 1}')
    with pytest.raises(BdError):
        bd.comments("zz-6q8")


def test_version_gate(bd: Bd, script: Script) -> None:
    script.say(fixture("version.json"))
    assert bd.check_version() == "1.3.1"
    script.say('{"version": "1.4.0"}')
    with pytest.raises(BdError) as e:
        bd.check_version()
    assert e.value.kind == "version"
    script.say('{"version": "1.2.9"}')
    with pytest.raises(BdError):
        bd.check_version()


def test_at_asks_another_tracker(script: Script) -> None:
    seen: list[str | None] = []

    def run(argv: list[str], cwd: str | None):
        seen.append(cwd)
        return script(argv, cwd)

    Bd("t", run=run).at("/x").ready()
    assert seen == ["/x"]
