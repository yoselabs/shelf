"""Command words, wrappers, write syntax, heredoc and exclusion stripping."""

from __future__ import annotations

import pytest

from any_shell_policy import Command, has_write_syntax, strip_excluded
from any_shell_policy.command import is_assign, name_of, strip_wrappers
from any_shell_policy.parse import strip_heredocs


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["ls"], ["ls"]),
        (["sudo", "pkill", "x"], ["pkill", "x"]),
        (["sudo", "-u", "root", "-E", "pkill", "x"], ["pkill", "x"]),
        (["sudo", "--user", "root", "pkill"], ["pkill"]),
        (["env", "-i", "A=1", "B=2", "git", "push"], ["git", "push"]),
        (["env", "-u", "A", "git"], ["git"]),
        (["nohup", "time", "nice", "-n", "5", "pkill", "x"], ["pkill", "x"]),
        (["timeout", "-s", "KILL", "5", "pkill", "x"], ["pkill", "x"]),
        (["/usr/bin/env", "xargs", "-n", "1", "-P", "4", "kill"], ["kill"]),
        (["env", "-S", "git push"], ["git", "push"]),
        (["env", "-Sgit push -f"], ["git", "push", "-f"]),
        (["env", "--split-string=sudo git push"], ["git", "push"]),
        (["env", "-S", "A=1 git push", "extra"], ["git", "push", "extra"]),
        (["env", "-S", "'unclosed"], ["'unclosed"]),
        (["sudo", "FOO=1", "git", "push"], ["git", "push"]),
        (["doas", "FOO=1", "git"], ["git"]),
        (["sudo", "--", "-weird"], ["-weird"]),
        (["sudo"], []),
        ([], []),
    ],
)
def test_strip_wrappers(argv: list[str], expected: list[str]) -> None:
    assert list(strip_wrappers(argv)) == expected


def test_command_name_and_words() -> None:
    cmd = Command(argv=("sudo", "/usr/bin/pkill", "-f", "x"))
    assert (cmd.name, cmd.words) == ("pkill", ("/usr/bin/pkill", "-f", "x"))
    assert Command().name == ""


def test_name_of_and_is_assign() -> None:
    assert name_of("/a/b/git") == "git"
    assert is_assign("A_1=x") and is_assign("A+=x") and is_assign("A=")
    assert not is_assign("=x") and not is_assign("--a=b") and not is_assign("1A=x")


@pytest.mark.parametrize(
    ("text", "writes"),
    [
        ("ls", False),
        ("echo x > f", True),
        ("echo x >> f", True),
        ("echo x &> f", True),
        ("echo `date`", True),
        ("echo $(date)", True),
        ('echo "$(date)"', True),
        ("diff <(a) <(b)", True),
        ("tee >(cat)", True),
        ("echo x > /dev/null 2>&1", False),
        ("echo x >&2", False),
        ("ls 2>/dev/null", False),
        ("echo x > /dev/null.txt", True),
        ("echo x >&2x", True),
        ("cat <<EOF\na > b\nEOF", False),
        ("cat > f <<EOF\nx\nEOF", True),
    ],
)
def test_has_write_syntax(text: str, writes: bool) -> None:
    assert has_write_syntax(text) is writes


def test_strip_heredocs_keeps_the_command_line() -> None:
    assert strip_heredocs("cat <<EOF\nbody\nEOF\nls") == "cat <<EOF\nls"
    assert strip_heredocs("cat <<A <<B\n1\nA\n2\nB\nls") == "cat <<A <<B\nls"
    assert strip_heredocs("echo '<<EOF'\nbody") == "echo '<<EOF'\nbody"
    assert strip_heredocs("echo 'open <<EOF\nbody") == "echo 'open <<EOF\nbody"


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["rg", "x", "--glob", "!.env*"], ["rg", "x"]),
        (["rg", "x", "--glob=!.env*"], ["rg", "x"]),
        (["rg", "x", "-g", "!.env*"], ["rg", "x"]),
        (["rg", "x", "-g", "*.py"], ["rg", "x", "*.py"]),
        (["grep", "-r", "x", "--exclude", ".env", "."], ["grep", "-r", "x", "."]),
        (["grep", "-r", "x", "--exclude-dir=.ssh"], ["grep", "-r", "x"]),
        (["find", ".", "-not", "-path", "*/.env"], ["find", "."]),
        (["find", ".", "!", "-name", ".env"], ["find", "."]),
        (["find", ".", "-name", ".env"], ["find", ".", "-name", ".env"]),
        (["git", "grep", "x", "--", ":!.env"], ["git", "grep", "x", "--"]),
        (["git", "grep", "x", ":(exclude).env"], ["git", "grep", "x"]),
        (["cat", ".env"], ["cat", ".env"]),
    ],
)
def test_strip_excluded(argv: list[str], expected: list[str]) -> None:
    assert list(strip_excluded(argv)) == expected
