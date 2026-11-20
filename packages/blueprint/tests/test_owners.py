"""One owner per fact: a second copy of a pinned fact fails `stack.one-owner` and names the owner (owners.toml)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint import owners
from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_ID = "stack.one-owner"
_PYPROJECT = '[project]\nname = "x"\nrequires-python = ">=3.12"\n\n[tool.uv]\nrequired-version = ">=0.10"\n'


def _row(repo: Repo) -> tuple[Verdict, str]:
    row = next(r for r in run(repo.root, concern="stack", env=repo.env).rows if r.id == _ID)
    return row.verdict, row.evidence


def _sound(repo: Repo) -> None:
    repo.write("pyproject.toml", _PYPROJECT)
    repo.write(".python-version", "3.12\n")
    repo.write("mise.toml", '[tools]\nuv = "0.13.0"\n')


def test_the_table_is_plain_text_and_every_fact_names_an_owner_and_a_reason() -> None:
    facts = owners.table()
    assert facts
    assert all(f.owner and f.why and f.copies for f in facts)


def test_each_fact_in_its_owner_alone_passes(repo: Repo) -> None:
    _sound(repo)
    assert _row(repo)[0] is Verdict.PASSING


def test_mise_pinning_python_fails_naming_python_version(repo: Repo) -> None:
    _sound(repo)
    repo.write("mise.toml", '[tools]\nuv = "0.13.0"\npython = "3.12.9"\n')
    verdict, evidence = _row(repo)
    assert verdict is Verdict.FAILING
    assert "the owner is .python-version" in evidence


def test_a_tool_versions_python_line_fails(repo: Repo) -> None:
    _sound(repo)
    repo.write(".tool-versions", "python 3.12.9\n")
    assert "the owner is .python-version" in _row(repo)[1]


def test_mise_pinning_dotnet_beside_global_json_fails_naming_global_json(repo: Repo) -> None:
    _sound(repo)
    repo.write("mise.toml", '[tools]\nuv = "0.13.0"\ndotnet = "10.0.401"\n')
    assert "the owner is global.json" in _row(repo)[1]


def test_an_exact_uv_required_version_is_a_second_copy_of_mises_pin(repo: Repo) -> None:
    _sound(repo)
    repo.write("pyproject.toml", _PYPROJECT.replace('">=0.10"', '"==0.13.0"'))
    assert "the owner is mise.toml" in _row(repo)[1]


def test_a_uv_floor_is_not_a_copy(repo: Repo) -> None:
    _sound(repo)
    assert _row(repo)[0] is Verdict.PASSING
