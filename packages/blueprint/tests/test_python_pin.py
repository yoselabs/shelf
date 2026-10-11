"""Python and uv version pins for python-uv repos: one pin, an honest range, a uv floor, CI that reads them."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from blueprint.model import Verdict
from blueprint.runner import run

if TYPE_CHECKING:
    from blueprint.testing import Repo

_PYPROJECT = '[project]\nname = "x"\nrequires-python = ">=3.12"\n\n[tool.uv]\nrequired-version = ">=0.10"\n'
_CI = "jobs:\n  check:\n    steps:\n      - uses: astral-sh/setup-uv@abc # v6\n      - run: uv sync --locked\n      - run: just check\n"


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


_TOOL_PYPROJECT = _PYPROJECT.replace('name = "x"', 'name = "mytool"') + '\n[project.scripts]\nmytool = "mytool:main"\n'
_LOCK = (
    'version = 1\n\n[[package]]\nname = "sqlite-sidecar"\nversion = "0.2.0"\n\n'
    '[[package]]\nname = "mytool"\nversion = "0.1.0"\nsource = { editable = "." }\n'
)
_TOOL_ROW = "stack.python-uv.uv-tool"


def _installed_tool(repo: Repo, versions: dict[str, str], *, installed: bool = True) -> None:
    """A uv whose `tool dir` holds an environment for mytool listing `versions` (name -> version)."""
    tools = repo.sysroot / "uv-tools"
    if installed:
        (tools / "mytool").mkdir(parents=True)
    listing = json.dumps([{"name": n, "version": v} for n, v in versions.items()])
    (repo.bin_dir / "uv").write_text(f"#!/bin/sh\nif [ \"$1\" = tool ]; then echo {tools}; exit 0; fi\ncat <<'EOF'\n{listing}\nEOF\n")
    (repo.bin_dir / "uv").chmod(0o755)


def _tool_row(repo: Repo) -> tuple[Verdict, str, str]:
    row = {r.id: r for r in run(repo.root, concern="stack", audit=True, env=repo.env).rows}[_TOOL_ROW]
    return row.verdict, row.evidence, row.remediation


def _application(repo: Repo, makefile: str = "check:\n\ttrue\n") -> None:
    repo.write("pyproject.toml", _TOOL_PYPROJECT)
    repo.write("uv.lock", _LOCK)
    repo.write("Makefile", makefile)


def test_a_tool_env_older_than_the_lock_fails_and_names_the_repos_reinstall_step(repo: Repo) -> None:
    # a2kay: src imported sqlite_sidecar.prepare (0.2.0) while the tool env kept 0.1.0; the daemon died on start.
    _application(repo, "check:\n\ttrue\ninstall:\n\tuv tool install --reinstall --editable .\n")
    _installed_tool(repo, {"sqlite-sidecar": "0.1.0", "mytool": "0.1.0"})
    verdict, evidence, remediation = _tool_row(repo)
    assert verdict is Verdict.FAILING
    assert "sqlite-sidecar 0.1.0 (lock 0.2.0)" in evidence
    assert "mytool 0.1.0" not in evidence  # the project itself is the lock's editable entry, not a dependency
    assert "make install" in remediation


def test_the_reinstall_step_is_a_justfile_recipe_when_the_gate_is_just(repo: Repo) -> None:
    repo.write("pyproject.toml", _TOOL_PYPROJECT)
    repo.write("uv.lock", _LOCK)
    repo.write("justfile", "check:\n    true\ninstall:\n    uv tool install --reinstall --editable .\n")
    _installed_tool(repo, {"sqlite-sidecar": "0.1.0"})
    assert "just install" in _tool_row(repo)[2]


def test_without_a_reinstall_step_the_remediation_asks_for_one_that_runs_after_a_lock_change(repo: Repo) -> None:
    _application(repo)
    _installed_tool(repo, {"sqlite-sidecar": "0.1.0"})
    remediation = _tool_row(repo)[2]
    assert "uv tool install --reinstall" in remediation
    assert "post-merge" in remediation


def test_a_tool_env_matching_the_lock_passes(repo: Repo) -> None:
    _application(repo)
    _installed_tool(repo, {"sqlite-sidecar": "0.2.0", "mytool": "0.1.0", "extra-only-in-env": "9.9"})
    assert _tool_row(repo)[0] is Verdict.PASSING


def test_a_tool_not_installed_on_this_machine_does_not_apply(repo: Repo) -> None:
    _application(repo)
    _installed_tool(repo, {}, installed=False)
    assert _tool_row(repo)[0] is Verdict.NOT_APPLICABLE


def test_the_tool_check_is_left_out_of_the_per_commit_run(repo: Repo) -> None:
    _application(repo)
    assert _TOOL_ROW not in {r.id for r in run(repo.root, concern="stack", env=repo.env).rows}
