"""Python and uv version pins for python-uv repos: one pin, an honest range, a uv floor, CI that reads them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_PYPROJECT = '[project]\nname = "x"\nrequires-python = ">=3.12"\n\n[tool.uv]\nrequired-version = ">=0.10"\n'
_CI = "jobs:\n  check:\n    steps:\n      - uses: astral-sh/setup-uv@abc # v6\n      - run: uv sync --locked\n      - run: make check\n"


_PIN_ROWS = {f"stack.python-uv.{n}" for n in ("python-pin", "python-range", "python-range-tested", "python-ci", "uv-version")}


def _rows(repo: Repo) -> dict[str, tuple[Verdict, str]]:
    return {r.id: (r.verdict, r.evidence) for r in run(repo.root, concern="stack", env=repo.env).rows if r.id in _PIN_ROWS}


def _sound(repo: Repo) -> None:
    repo.write("pyproject.toml", _PYPROJECT)
    repo.write("uv.lock", "")
    repo.write(".python-version", "3.12\n")
    repo.write(".github/workflows/check.yml", _CI)


def _verdict(repo: Repo, row: str) -> Verdict:
    return _rows(repo)[f"stack.python-uv.{row}"][0]


def test_a_sound_setup_passes_every_pin_row(repo: Repo) -> None:
    _sound(repo)
    rows = _rows(repo)
    assert set(rows) == _PIN_ROWS
    assert {v for v, _ in rows.values()} == {Verdict.PASSING}


def test_no_pin_file_is_not_set_up(repo: Repo) -> None:
    _sound(repo)
    (repo.root / ".python-version").unlink()
    assert _verdict(repo, "python-pin") is Verdict.NOT_SET_UP


def test_a_patch_level_pin_fails(repo: Repo) -> None:
    _sound(repo)
    repo.write(".python-version", "3.12.7\n")
    assert _verdict(repo, "python-pin") is Verdict.FAILING


def test_a_pin_below_the_range_fails(repo: Repo) -> None:
    _sound(repo)
    repo.write(".python-version", "3.11\n")
    assert _verdict(repo, "python-pin") is Verdict.FAILING


def test_a_capped_range_fails(repo: Repo) -> None:
    _sound(repo)
    repo.write("pyproject.toml", _PYPROJECT.replace('">=3.12"', '">=3.12,<3.14"'))
    assert _verdict(repo, "python-range") is Verdict.FAILING


def test_a_lower_bound_below_the_pin_needs_a_ci_run_on_it(repo: Repo) -> None:
    _sound(repo)
    repo.write("pyproject.toml", _PYPROJECT.replace('">=3.12"', '">=3.11"'))
    verdict, evidence = _rows(repo)["stack.python-uv.python-range-tested"]
    assert verdict is Verdict.FAILING
    assert "3.11" in evidence
    repo.write(".github/workflows/check.yml", _CI + "      - run: uv run --python 3.11 pytest\n")
    assert _verdict(repo, "python-range-tested") is Verdict.PASSING


def test_a_workspace_member_lower_than_the_pin_counts(repo: Repo) -> None:
    _sound(repo)
    repo.write("pyproject.toml", '[tool.uv]\nrequired-version = ">=0.10"\n\n[tool.uv.workspace]\nmembers = ["packages/*"]\n')
    repo.write("packages/a/pyproject.toml", '[project]\nname = "a"\nrequires-python = ">=3.10"\n')
    verdict, evidence = _rows(repo)["stack.python-uv.python-range-tested"]
    assert verdict is Verdict.FAILING
    assert "packages/a" in evidence


def test_ci_hard_coding_python_fails(repo: Repo) -> None:
    _sound(repo)
    setup_python = '      - uses: actions/setup-python@x\n        with:\n          python-version: "3.12"\n'
    repo.write(".github/workflows/check.yml", _CI.replace("      - run: uv sync", setup_python + "      - run: uv sync"))
    assert _verdict(repo, "python-ci") is Verdict.FAILING


def test_no_uv_floor_is_not_set_up(repo: Repo) -> None:
    _sound(repo)
    repo.write("pyproject.toml", '[project]\nname = "x"\nrequires-python = ">=3.12"\n')
    assert _verdict(repo, "uv-version") is Verdict.NOT_SET_UP
