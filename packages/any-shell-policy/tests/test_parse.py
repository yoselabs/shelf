"""parse: quote-aware splitting, shell -c unwrapping, and the bypass corpus."""

from __future__ import annotations

import pytest

from any_shell_policy import Command, parse


def argvs(text: str) -> list[tuple[str, ...]] | None:
    cmds = parse(text)
    return None if cmds is None else [c.argv for c in cmds]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", []),
        ("   \n  ", []),
        ("ls -la", [("ls", "-la")]),
        ("a | b || c && d ; e\nf", [("a",), ("b",), ("c",), ("d",), ("e",), ("f",)]),
        ("a & b", [("a",), ("b",)]),
        ("a |& b", [("a",), ("b",)]),
        ("(a; b)", [("a",), ("b",)]),
        ("echo $(pkill x)", [("echo",), ("pkill", "x")]),
        ("echo `pkill x`", [("echo",), ("pkill", "x")]),
        ("echo 'a;b' \"c|d\" e\\;f", [("echo", "a;b", "c|d", "e;f")]),
        ("echo '' x", [("echo", "", "x")]),
        ("echo a#b # comment ; pkill x", [("echo", "a#b")]),
        ("echo a\\\nb", [("echo", "ab")]),
        ('echo "a\\"b" "c\\d"', [("echo", 'a"b', "c\\d")]),
        ("f() { pkill x; }", [("f",), ("pkill", "x")]),
        ("for f in a b; do rm $f; done", [("rm", "$f")]),
        ("while read x; do echo $x; done < in", [("read", "x"), ("echo", "$x"), ()]),
        ("if test -f x; then echo y; else echo n; fi", [("test", "-f", "x"), ("echo", "y"), ("echo", "n")]),
    ],
)
def test_split(text: str, expected: list[tuple[str, ...]]) -> None:
    assert argvs(text) == expected


def test_assigns_split_from_argv() -> None:
    [cmd] = parse("FOO=1 BAR+=x env_not=1 ls") or []
    assert (cmd.assigns, cmd.argv) == (("FOO=1", "BAR+=x", "env_not=1"), ("ls",))
    [bare] = parse("FOO=1") or []
    assert (bare.assigns, bare.argv) == (("FOO=1",), ())


@pytest.mark.parametrize(
    ("text", "redirects"),
    [
        ("echo x > out", (">out",)),
        ("echo x >>out", (">>out",)),
        ("echo x 2> err", ("2>err",)),
        ("echo x &> all", ("&>all",)),
        ("echo x > /dev/null 2>&1", ()),
        ("echo x >&2", ()),
        ("echo x >&file", (">&file",)),
        ("echo x < in", ("<in",)),
        ("echo x < /dev/null", ()),
        ("echo x '>' y", ()),
    ],
)
def test_redirects(text: str, redirects: tuple[str, ...]) -> None:
    [cmd] = parse(text) or []
    assert cmd.redirects == redirects
    assert cmd.argv[0] == "echo"


def test_output_redirects_only_writes() -> None:
    [cmd] = parse("cat < in > out 2>>log") or []
    assert cmd.output_redirects == (">out", "2>>log")


def test_bare_redirect_is_a_command() -> None:
    assert parse("> file") == [Command(redirects=(">file",))]


def test_heredoc_body_is_not_commands() -> None:
    text = "cat > f <<'EOF'\npkill x\n$(boom)\nEOF\nls"
    cmds = parse(text) or []
    assert [c.argv for c in cmds] == [("cat",), ("ls",)]
    assert cmds[0].stdin == "pkill x\n$(boom)\n"


def test_heredoc_inside_quotes_does_not_hide_the_next_line() -> None:
    assert argvs('echo "<<EOF"\npkill x') == [("echo", "<<EOF"), ("pkill", "x")]


def test_heredoc_dash_strips_tabs_and_unterminated_runs_to_end() -> None:
    assert argvs("cat <<-X\n\tbody\n\tX\nls") == [("cat",), ("ls",)]
    assert argvs("cat <<X\npkill x") == [("cat",)]


# The bypass corpus: every spelling that once hid a command from a regex guard.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("pkill x", [("pkill", "x")]),
        ("/usr/bin/pkill x", [("/usr/bin/pkill", "x")]),
        ("sudo pkill x", [("sudo", "pkill", "x")]),
        ("echo ok; pkill x", [("echo", "ok"), ("pkill", "x")]),
        ("echo ok&&pkill x", [("echo", "ok"), ("pkill", "x")]),
        ("echo 'xzx;pkill'", [("echo", "xzx;pkill")]),
        ("echo \"a|b\" | grep 'x;y'", [("echo", "a|b"), ("grep", "x;y")]),
        ("rg x '\"'!'\"\\.env*'", [("rg", "x", '"!"\\.env*')]),
        ("rg x --glob '!'\\.env", [("rg", "x", "--glob", "!.env")]),
    ],
)
def test_corpus_splitting(text: str, expected: list[tuple[str, ...]]) -> None:
    assert argvs(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "sh -c 'pkill x'",
        'bash -lc "pkill x"',
        "bash -o pipefail -c 'pkill x'",
        "sudo -u root bash -c 'pkill x'",
        "env FOO=1 sh -c 'pkill x'",
        "xargs -n1 sh -c 'pkill x'",
        "echo hi && sh -c 'echo; pkill x'",
        "eval 'pkill x'",
        "eval pkill x",
        "bash <<EOF\npkill x\nEOF",
        "bash <<< 'pkill x'",
        "sh -c \"sh -c 'pkill x'\"",
        'sh -c "sh -c \\"sh -c \'pkill x\'\\""',
    ],
)
def test_shell_c_is_looked_through(text: str) -> None:
    names = [c.name for c in parse(text) or []]
    assert "pkill" in names
    assert not {"sh", "bash", "eval"} & set(names)


def test_depth_three_parses_and_depth_four_fails_closed() -> None:
    depth3 = 'sh -c "sh -c \'sh -c \\"pkill x\\"\'"'
    assert argvs(depth3) == [("pkill", "x")]
    depth4 = 'sh -c "sh -c \'sh -c \\"sh -c pkill\\"\'"'
    assert parse(depth4) is None


def test_shell_running_a_file_stays_a_command() -> None:
    assert argvs("bash script.sh -c") == [("bash", "script.sh", "-c")]
    assert argvs("echo x | bash") == [("echo", "x"), ("bash",)]


def test_shell_c_keeps_its_own_redirect() -> None:
    cmds = parse("sh -c 'ls' > out") or []
    assert [(c.argv, c.redirects) for c in cmds] == [((), (">out",)), (("ls",), ())]


@pytest.mark.parametrize("text", ["echo 'open", 'echo "open', "echo $'\\x70kill'", "sh -c 'echo \"open'"])
def test_unparseable_returns_none(text: str) -> None:
    assert parse(text) is None
