"""The --help tree walk, run on a small sample CLI: a good one passes, each defect is named."""

from __future__ import annotations

import argparse

import pytest
from verb_cli.testing import assert_help_tree


def _cli(
    *,
    sub_help: str | None = "list things",
    sub_description: str | None = "List the things.",
    flag_help: str | None = "a flag",
    top_description: str | None = "The sample.",
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sample", description=top_description)
    parser.add_argument("--verbose", action="store_true", help="more output")
    subs = parser.add_subparsers(dest="cmd", required=True)
    ls = subs.add_parser("list", help=sub_help, description=sub_description)
    ls.add_argument("--flag", help=flag_help)
    ls.add_argument("name", help="what to list")
    grp = subs.add_parser("group", help="a group", description="A group.")
    inner = grp.add_subparsers(dest="sub", required=True)
    inner.add_parser("leaf", help="a leaf", description="A leaf.")
    return parser


def test_a_described_tree_passes() -> None:
    assert_help_tree(_cli())


def test_a_flag_without_help_is_named() -> None:
    with pytest.raises(AssertionError, match=r"sample list.*--flag"):
        assert_help_tree(_cli(flag_help=None))


def test_a_subparser_with_help_none_is_missing_from_the_listing() -> None:
    with pytest.raises(AssertionError, match=r"list.*listing"):
        assert_help_tree(_cli(sub_help=None))


def test_a_command_without_a_description_is_named() -> None:
    with pytest.raises(AssertionError, match=r"sample list.*description"):
        assert_help_tree(_cli(sub_description=None))


def test_the_root_needs_a_description_too() -> None:
    with pytest.raises(AssertionError, match=r"description"):
        assert_help_tree(_cli(top_description=None))
