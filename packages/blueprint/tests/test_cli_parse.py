"""Every console script and directly run script has a test that runs it with `--help` (ADR 0025)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo


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


def test_typer_counts_as_parsing(repo: Repo) -> None:
    repo.write("tools/b.py", "import typer\nif __name__ == '__main__':\n    typer.run(print)\n")
    verdict, evidence = _direct_row(repo)
    assert verdict is Verdict.FAILING
    assert "tools/b.py" in evidence


def test_a_script_under_tests_is_not_counted(repo: Repo) -> None:
    repo.write("tests/helper.py", _PARSING_SCRIPT)
    assert _direct_row(repo)[0] is Verdict.NOT_APPLICABLE


def test_the_finding_says_untracked_tests_are_not_read(repo: Repo) -> None:
    # a2kay 2026-10-12: a new, not yet added test file read as "no test runs X".
    assert "tracked" in _help_row(repo, 'tool = "x.cli:main"\n')[1]


def test_the_lenient_parsing_row_is_gone(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    repo.write("uv.lock", "")
    repo.write("src/x/cli.py", "p.parse_known_args()\n")
    repo.commit()
    assert "stack.python-uv.cli-parse" not in {r.id for r in run(repo.root, concern="stack", env=repo.env).rows}


def test_an_internal_entry_script_with_a_fixed_argv_is_not_a_command(repo: Repo) -> None:
    repo.write("tools/hook.py", 'import sys\n\nif __name__ == "__main__":\n    print(sys.argv[1])\n')
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    repo.write("uv.lock", "")
    repo.commit()
    row = next(r for r in run(repo.root, concern="stack", env=repo.env).rows if r.id == _HELP_ROW)
    assert row.verdict is Verdict.NOT_APPLICABLE


def test_a_script_with_an_argument_parser_is_a_command_and_needs_the_help_test(repo: Repo) -> None:
    repo.write("tools/run.py", 'import argparse\n\nif __name__ == "__main__":\n    argparse.ArgumentParser().parse_args()\n')
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    repo.write("uv.lock", "")
    repo.commit()
    row = next(r for r in run(repo.root, concern="stack", env=repo.env).rows if r.id == _HELP_ROW)
    assert row.verdict is Verdict.FAILING
