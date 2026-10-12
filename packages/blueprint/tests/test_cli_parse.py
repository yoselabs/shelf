"""A CLI rejects flags it does not know: `parse_known_args` and `add_help=False` swallow them (a2kay 2026-10, twice)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_ROW = "stack.python-uv.cli-parse"


def _row(repo: Repo) -> tuple[Verdict, str]:
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    repo.write("uv.lock", "")
    repo.commit()
    row = next(r for r in run(repo.root, concern="stack", env=repo.env).rows if r.id == _ROW)
    return row.verdict, row.evidence


def test_strict_parsing_passes(repo: Repo) -> None:
    repo.write("src/x/cli.py", "import argparse\nargs = argparse.ArgumentParser().parse_args()\n")
    assert _row(repo)[0] is Verdict.PASSING


def test_lenient_parsing_fails_and_names_the_line(repo: Repo) -> None:
    repo.write("src/x/serve.py", "import argparse\np = argparse.ArgumentParser(add_help=False)\nargs, _ = p.parse_known_args()\n")
    verdict, evidence = _row(repo)
    assert verdict is Verdict.FAILING
    assert "src/x/serve.py:2" in evidence
    assert "src/x/serve.py:3" in evidence


def test_a_waived_two_stage_pre_parser_passes(repo: Repo) -> None:
    repo.write(
        "src/x/verbs.py",
        "import argparse\n"
        "pre = argparse.ArgumentParser(add_help=False)  # lenient: globals pre-parser; the rest goes to a strict parse_args\n"
        "# lenient: globals pre-parser, see above\n"
        "known, rest = pre.parse_known_args()\n",
    )
    assert _row(repo)[0] is Verdict.PASSING


def test_tests_may_parse_leniently(repo: Repo) -> None:
    repo.write("tests/test_cli.py", "import argparse\nargparse.ArgumentParser().parse_known_args([])\n")
    assert _row(repo)[0] is Verdict.PASSING


def test_one_waiver_covers_the_rest_of_its_function_and_no_further(repo: Repo) -> None:
    repo.write(
        "tools/stack.py",
        "import argparse\n"
        "def parse(argv):\n"
        "    # lenient: an SSH forced command; leftovers are refused below, --help would only echo usage to the client\n"
        "    p = argparse.ArgumentParser(add_help=False)\n"
        "    sub = p.add_subparsers()\n"
        "    sub.add_parser('deploy', add_help=False)\n"
        "    ns, extra = p.parse_known_args(argv)\n"
        "def other(argv):\n"
        "    return argparse.ArgumentParser().parse_known_args(argv)\n",
    )
    verdict, evidence = _row(repo)
    assert verdict is Verdict.FAILING
    assert evidence.endswith("tools/stack.py:9")


def test_a_docstring_or_comment_naming_the_pattern_is_not_parsing(repo: Repo) -> None:
    text = '"""Never `parse_known_args` or `add_help=False`."""\n# add_help=False swallows --help\nX = "p.parse_known_args()"\n'
    repo.write("src/x/doc.py", text)
    assert _row(repo)[0] is Verdict.PASSING
