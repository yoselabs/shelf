"""A set of verbs becomes one parser: subcommands, positionals, choices, a shared parameter class."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Annotated, Literal

import pytest
from pydantic import Field
from verb_cli import POSITIONAL, VerbCli, VerbCliError, flags_of
from verb_cli.testing import assert_help_tree


@dataclass(frozen=True)
class Target:
    repo: Annotated[str, Field(description="the repository")] = "."
    kb: Annotated[str | None, Field(description="the knowledge base")] = None
    rev: Annotated[str | None, Field(description="a revision")] = None


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


def show(target: Target, address: Annotated[str, POSITIONAL], *, mode: Literal["short", "full"] = "short") -> dict[str, object]:
    """Show one thing.

    More text.
    """
    return {"repo": target.repo, "address": address, "mode": mode, "rev": target.rev}


def link(
    target: Target, before: Annotated[str, POSITIONAL], after: Annotated[str | None, POSITIONAL] = None, *words: Annotated[str, POSITIONAL]
) -> tuple:
    """Link things."""
    return (target.kb, before, after, words)


def paint(color: Color = Color.RED, *, count: int = 1) -> tuple[Color, int]:
    """Paint it."""
    return color, count


def pair(a: Annotated[str, POSITIONAL], /, b: str = "x") -> tuple[str, str]:
    """Positional-only."""
    return a, b


def _cli() -> VerbCli:
    return VerbCli({"show": show, "link": link, "paint": paint, "pair": pair}, shared=Target)


def test_a_verb_is_a_subcommand_and_shared_flags_are_folded_into_it() -> None:
    inv = _cli().parse(["show", "doc:a#b", "--repo", "/r", "--rev", "abc"])
    assert inv.name == "show"
    assert inv.call() == {"repo": "/r", "address": "doc:a#b", "mode": "short", "rev": "abc"}
    assert inv.shared == Target(repo="/r", rev="abc")


def test_a_literal_is_a_choice_not_a_json_flag() -> None:
    assert _cli().parse(["show", "x", "--mode", "full"]).call()["mode"] == "full"
    with pytest.raises(SystemExit):
        _cli().parse(["show", "x", "--mode", "nope"])


def test_optional_and_variadic_positionals_reach_the_call_by_position() -> None:
    assert _cli().parse(["link", "a"]).call() == (None, "a", None, ())
    assert _cli().parse(["link", "a", "b", "w1", "w2", "--kb", "k"]).call() == ("k", "a", "b", ("w1", "w2"))


def test_an_enum_is_a_choice_by_value_and_comes_back_as_the_member() -> None:
    assert _cli().parse(["paint", "--color", "blue", "--count", "2"]).call() == (Color.BLUE, 2)
    assert _cli().parse(["paint"]).call() == (Color.RED, 1)


def test_positional_only_parameters_are_called_by_position() -> None:
    assert _cli().parse(["pair", "q"]).call() == ("q", "x")


def test_the_help_tree_explains_itself() -> None:
    assert_help_tree(_cli().parser(prog="ogy"))


def test_a_verbs_own_specs_exclude_the_shared_parameter() -> None:
    assert [s.dest for s in _cli().specs("show")] == ["address", "mode"]


def test_a_verb_parameter_that_clashes_with_a_shared_one_is_refused() -> None:
    def bad(repo: str = "x") -> None:
        """Bad."""

    with pytest.raises(VerbCliError):
        VerbCli({"bad": bad}, shared=Target)


def test_choices_are_off_by_default_so_a_literal_stays_one_json_flag() -> None:
    assert flags_of(show)[2].needs_json is True
    assert flags_of(show, choices=True)[2].choices == ("short", "full")
