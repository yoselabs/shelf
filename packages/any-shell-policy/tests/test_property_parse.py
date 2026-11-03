"""Property tests: the round trip through shlex.join, quoted separators, and no input raises."""

from __future__ import annotations

import shlex

from hypothesis import given, settings
from hypothesis import strategies as st

from any_shell_policy import has_write_syntax, parse
from any_shell_policy.parse import strip_heredocs

# Any printable word, newlines included; NUL cannot appear in a shell word.
_WORD = st.text(st.characters(blacklist_characters="\x00", blacklist_categories=("Cs",)), min_size=1, max_size=12)
_SYNTAX = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}", "for", "select", "case", "done", "fi", "esac"}
_SEPARATORS = ["|", "||", "&&", ";", "&", "\n", "(", ")", "`", "$(", ">", "<", ";;", "#"]


@given(st.lists(_WORD, min_size=1, max_size=6))
def test_parse_of_joined_argv_is_that_argv(argv: list[str]) -> None:
    cmds = parse(shlex.join(argv))
    assert cmds is not None
    assert [c.argv for c in cmds if c.argv] == [tuple(argv)] or _keyword_or_assign_head(argv)


def _keyword_or_assign_head(argv: list[str]) -> bool:
    # A leading `if`, `FOO=1`, `for`... is shell syntax, not an argument: the property is about plain commands.
    return argv[0] in _SYNTAX or "=" in argv[0]


@given(st.lists(_WORD, min_size=1, max_size=4), st.sampled_from(_SEPARATORS))
def test_a_quoted_separator_never_splits(argv: list[str], sep: str) -> None:
    word = f"x{sep}y"
    cmds = parse(shlex.join(["echo", word, *argv]))
    assert cmds is not None
    assert [c.argv for c in cmds] == [("echo", word, *argv)]
    assert all(not c.redirects for c in cmds)


@given(st.text(max_size=200))
@settings(max_examples=300)
def test_no_input_raises(text: str) -> None:
    parse(text)
    strip_heredocs(text)
    has_write_syntax(text)


_PIECES = ["a", "'", '"', "\\", " ", "$", "(", ")", "|", ";", "&", "<", ">", "\n", "#", "`", "-c", "sh", "EOF", "<<"]


@given(st.lists(st.sampled_from(_PIECES), max_size=40))
@settings(max_examples=500)
def test_no_shell_shaped_input_raises(parts: list[str]) -> None:
    text = "".join(parts)
    parse(text)
    parse(f"sh -c {shlex.quote(text)}")
    strip_heredocs(text)
    has_write_syntax(text)
