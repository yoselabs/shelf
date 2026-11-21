from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from any_arch import Row, Rule, check, debt, debt_text, plant, rows
from any_arch.__main__ import main
from any_arch.rule import findings
from any_arch.source import sources

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from any_arch import Hit, Source


def _prints(source: Source) -> Iterable[Hit]:
    """Each `print(...)` call is a hit keyed by its package."""
    for node in ast.walk(source.tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
            yield source.package, node.lineno


def _rule(table: dict[str, Row], kinds: tuple[str, ...] = ()) -> Rule:
    return Rule("prints", "use the log", _prints, table, kinds)


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_findings_groups_the_lines_of_each_key(tmp_path: Path) -> None:
    _write(tmp_path, "packages/a/src/a/m.py", "print(1)\nx = 1\nprint(2)\n")
    _write(tmp_path, "packages/b/src/b/m.py", "print(3)\n")
    assert findings(_rule({}), tmp_path) == {"a": [1, 3], "b": [1]}


def test_a_file_outside_the_scope_is_not_scanned(tmp_path: Path) -> None:
    _write(tmp_path, "packages/a/tests/test_m.py", "print(1)\n")
    assert findings(_rule({}), tmp_path) == {}


def test_scope_may_name_other_trees_and_a_file_outside_packages_has_no_package(tmp_path: Path) -> None:
    _write(tmp_path, "tools/t.py", "print(1)\n")
    wide = Rule("prints", "fix", _prints, {}, scope=("tools/*.py",))
    assert findings(wide, tmp_path) == {"": [1]}


def test_a_file_is_parsed_once_and_again_after_it_changes(tmp_path: Path) -> None:
    path = _write(tmp_path, "packages/a/src/a/m.py", "x = 1\n")
    scope = ("packages/*/src/**/*.py",)
    first = sources(tmp_path, scope)[0].tree
    assert sources(tmp_path, scope)[0].tree is first
    path.write_text("x = 22\n", encoding="utf-8")
    assert sources(tmp_path, scope)[0].tree is not first


def test_a_clean_repo_with_matching_rows_passes(tmp_path: Path) -> None:
    _write(tmp_path, "packages/a/src/a/m.py", "print(1)\nprint(2)\n")
    check(_rule({"a": Row("debt: log it", 2)}), tmp_path)
    check(_rule({"a": Row("debt: log it")}), tmp_path)


def test_a_new_hit_fails_with_the_fix_text_and_its_lines(tmp_path: Path) -> None:
    _write(tmp_path, "packages/a/src/a/m.py", "print(1)\n")
    with pytest.raises(AssertionError, match=r"prints: use the log\nnew: a at lines \[1\]"):
        check(_rule({}), tmp_path)


def test_a_hit_beyond_an_exact_count_fails(tmp_path: Path) -> None:
    _write(tmp_path, "packages/a/src/a/m.py", "print(1)\nprint(2)\n")
    with pytest.raises(AssertionError, match="over: a has 2 hits, its row allows 1"):
        check(_rule({"a": Row("debt: x", 1)}), tmp_path)


def test_a_row_without_a_hit_is_stale(tmp_path: Path) -> None:
    _write(tmp_path, "packages/a/src/a/m.py", "x = 1\n")
    with pytest.raises(AssertionError, match="stale: gone has no hit"):
        check(_rule({"gone": Row("debt: x")}), tmp_path)


def test_a_row_counting_more_than_found_is_stale(tmp_path: Path) -> None:
    _write(tmp_path, "packages/a/src/a/m.py", "print(1)\n")
    with pytest.raises(AssertionError, match="stale: a has 1 hits, its row says 3"):
        check(_rule({"a": Row("debt: x", 3)}), tmp_path)


@pytest.mark.parametrize("reason", ["", "   ", "no prefix", "other: x"])
def test_a_row_needs_a_reason_with_an_allowed_prefix(tmp_path: Path, reason: str) -> None:
    _write(tmp_path, "packages/a/src/a/m.py", "print(1)\n")
    with pytest.raises(AssertionError, match="reason: a needs"):
        check(_rule({"a": Row(reason)}, kinds=("debt", "outcome")), tmp_path)


def test_without_kinds_any_non_blank_reason_passes(tmp_path: Path) -> None:
    _write(tmp_path, "packages/a/src/a/m.py", "print(1)\n")
    check(_rule({"a": Row("whatever")}), tmp_path)


def test_plant_returns_what_the_rule_finds_in_the_planted_source(tmp_path: Path) -> None:
    assert plant(_rule({}), tmp_path, "print(1)\n") == {"pkg": [1]}
    assert plant(_rule({}), tmp_path, "print(1)\n\nprint(2)\n", path="packages/q/src/q/n.py") == {"pkg": [1], "q": [1, 3]}


def test_rows_shares_one_reason_and_a_pair_sets_an_exact_count() -> None:
    assert rows("debt: r", "a", ("b", 2)) == {"a": Row("debt: r"), "b": Row("debt: r", 2)}


def test_debt_lists_only_debt_rows_grouped_by_rule() -> None:
    owed = Rule("one", "f", _prints, {**rows("debt: fix a", "a"), **rows("outcome: ok", "b")})
    clean = Rule("two", "f", _prints, rows("outcome: ok", "c"))
    other = Rule("three", "f", _prints, rows("debt: fix d", ("d", 2)))
    assert debt(owed, clean, other) == {"one": {"a": "debt: fix a"}, "three": {"d": "debt: fix d"}}
    assert debt_text(owed, clean, other) == "one (1)\n  a: fix a\nthree (1)\n  d: fix d"


def test_the_command_prints_the_debt_of_the_rules_a_module_defines(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    module = _write(
        tmp_path,
        "test_arch_x.py",
        "from any_arch import Rule, rows\nRULE = Rule('x', 'fix', lambda s: [], rows('debt: owed', 'k'))\n",
    )
    assert main([str(module)]) == 0
    assert capsys.readouterr().out == "x (1)\n  k: owed\n"


def test_the_command_refuses_a_path_it_cannot_load(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="cannot load"):
        main([str(tmp_path / "not_python.txt")])
