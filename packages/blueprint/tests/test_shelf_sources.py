"""One snapshot, one spelling: mixed shelf tags or URL spellings and re-pinning overrides fail `stack.shelf-sources`; init normalizes."""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

from blueprint import init, shelf_sources
from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    import pytest
    from blueprint.testing import Repo

_ID = "stack.shelf-sources"
_URL = "https://github.com/yoselabs/shelf"


def _src(name: str, tag: str, url: str = _URL) -> str:
    return f'{name} = {{ git = "{url}", subdirectory = "packages/{name}", tag = "{tag}" }}\n'


def _pyproject(*sources: str, overrides: str = "") -> str:
    return '[project]\nname = "x"\nversion = "0"\nrequires-python = ">=3.12"\n\n[tool.uv.sources]\n' + "".join(sources) + overrides


def _row(repo: Repo) -> tuple[Verdict, str]:
    row = next(r for r in run(repo.root, concern="stack", env=repo.env).rows if r.id == _ID)
    return row.verdict, row.evidence


def test_sources_at_one_tag_and_one_spelling_pass(repo: Repo) -> None:
    repo.write("pyproject.toml", _pyproject(_src("any-a", "blueprint-v0.7.0"), _src("any-b", "blueprint-v0.7.0")))
    assert _row(repo)[0] is Verdict.PASSING


def test_mixed_tags_fail_naming_the_snapshot_tag(repo: Repo) -> None:
    repo.write("pyproject.toml", _pyproject(_src("any-a", "any-a-v0.2.0"), _src("any-b", "any-b-v0.1.0")))
    verdict, evidence = _row(repo)
    assert verdict is Verdict.FAILING
    assert shelf_sources.snapshot_tag() in evidence


def test_a_dot_git_spelling_fails(repo: Repo) -> None:
    repo.write("pyproject.toml", _pyproject(_src("any-a", "t"), _src("any-b", "t", _URL + ".git")))
    verdict, evidence = _row(repo)
    assert verdict is Verdict.FAILING
    assert "any-b" in evidence
    assert "any-a" not in evidence.split(";")[0]


def test_an_override_that_re_pins_a_shelf_package_fails(repo: Repo) -> None:
    pins = '\n[tool.uv]\noverride-dependencies = ["any-a>=0.1", "other>=1"]\n'
    repo.write("pyproject.toml", _pyproject(_src("any-a", "t"), overrides=pins))
    verdict, evidence = _row(repo)
    assert verdict is Verdict.FAILING
    assert "re-pins the shelf package any-a" in evidence
    assert "other" not in evidence


def test_a_repo_with_no_shelf_source_is_not_concerned(repo: Repo) -> None:
    repo.write("pyproject.toml", _pyproject())
    assert _row(repo)[0] is Verdict.NOT_APPLICABLE


def test_init_writes_every_shelf_source_at_the_snapshot_tag_and_canonical_spelling(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    repo.write("pyproject.toml", _pyproject(_src("any-a", "any-a-v0.2.0", _URL + ".git"), _src("any-b", "any-b-v0.1.0")))
    repo.write("uv.lock", "")
    init.run(repo.root, hooks=False, beads=False, env=repo.env)
    assert "the shelf git sources" in capsys.readouterr().out
    written = tomllib.loads((repo.root / "pyproject.toml").read_text())["tool"]["uv"]["sources"]
    assert {(s["git"], s["tag"]) for s in written.values()} == {(_URL, shelf_sources.snapshot_tag())}
    assert written["any-a"]["subdirectory"] == "packages/any-a"
