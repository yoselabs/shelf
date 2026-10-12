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


_HELP_ROW = "stack.python-uv.cli-help-tested"


def _help_row(repo: Repo, scripts: str) -> tuple[Verdict, str]:
    repo.write("pyproject.toml", f'[project]\nname = "x"\n\n[project.scripts]\n{scripts}')
    repo.write("uv.lock", "")
    repo.commit()
    row = next(r for r in run(repo.root, concern="stack", env=repo.env).rows if r.id == _HELP_ROW)
    return row.verdict, row.evidence


def test_each_console_script_needs_a_test_running_it_with_help(repo: Repo) -> None:
    repo.write("tests/test_cli.py", 'def test_help(run):\n    assert run("tool", "--help").code == 0\n')
    verdict, evidence = _help_row(repo, 'tool = "x.cli:main"\nserve = "x.serve:main"\n')
    assert verdict is Verdict.FAILING
    assert "serve" in evidence
    assert "tool," not in evidence


def test_scripts_with_help_tests_pass(repo: Repo) -> None:
    repo.write("tests/test_cli.py", 'import subprocess\nsubprocess.run(["tool", "--help"], check=True)\n')
    assert _help_row(repo, 'tool = "x.cli:main"\n')[0] is Verdict.PASSING


def test_a_repo_without_console_scripts_has_nothing_to_help(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    repo.write("uv.lock", "")
    repo.commit()
    row = next(r for r in run(repo.root, concern="stack", env=repo.env).rows if r.id == _HELP_ROW)
    assert row.verdict is Verdict.NOT_APPLICABLE


def test_a_workspace_members_console_scripts_count_too(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "root"\n\n[tool.uv.workspace]\nmembers = ["packages/*"]\n')
    repo.write("uv.lock", "")
    repo.write("packages/tool/pyproject.toml", '[project]\nname = "tool"\n\n[project.scripts]\ntool = "tool.cli:main"\n')
    repo.commit()
    row = next(r for r in run(repo.root, concern="stack", env=repo.env).rows if r.id == _HELP_ROW)
    assert row.verdict is Verdict.FAILING
    assert "tool" in row.evidence


_PARSING_SCRIPT = "import argparse\n\ndef main():\n    argparse.ArgumentParser().parse_args()\n\nif __name__ == '__main__':\n    main()\n"


def _direct_row(repo: Repo) -> tuple[Verdict, str]:
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    repo.write("uv.lock", "")
    repo.commit()
    row = next(r for r in run(repo.root, concern="stack", env=repo.env).rows if r.id == _HELP_ROW)
    return row.verdict, row.evidence


def test_a_directly_run_script_that_parses_arguments_needs_a_help_test(repo: Repo) -> None:
    repo.write("tools/x.py", _PARSING_SCRIPT)
    verdict, evidence = _direct_row(repo)
    assert verdict is Verdict.FAILING
    assert "tools/x.py" in evidence


def test_a_test_running_the_script_with_help_passes(repo: Repo) -> None:
    repo.write("tools/x.py", _PARSING_SCRIPT)
    repo.write("tests/test_x.py", 'import subprocess\nsubprocess.run(["python", "tools/x.py", "--help"], check=True)\n')
    assert _direct_row(repo)[0] is Verdict.PASSING


def test_a_main_script_that_parses_nothing_is_not_a_command(repo: Repo) -> None:
    repo.write("tools/y.py", "def main():\n    print('hi')\n\nif __name__ == '__main__':\n    main()\n")
    assert _direct_row(repo)[0] is Verdict.NOT_APPLICABLE


def test_sys_argv_and_typer_count_as_parsing(repo: Repo) -> None:
    repo.write("tools/a.py", "import sys\nif __name__ == '__main__':\n    print(sys.argv)\n")
    repo.write("tools/b.py", "import typer\nif __name__ == '__main__':\n    typer.run(print)\n")
    verdict, evidence = _direct_row(repo)
    assert verdict is Verdict.FAILING
    assert "tools/a.py" in evidence
    assert "tools/b.py" in evidence


def test_a_script_under_tests_is_not_counted(repo: Repo) -> None:
    repo.write("tests/helper.py", _PARSING_SCRIPT)
    assert _direct_row(repo)[0] is Verdict.NOT_APPLICABLE
