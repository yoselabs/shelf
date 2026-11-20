"""`blueprint init`: detect the stack, audit, plan, apply only what is missing; no shelf clone; never overwrite; end with what is left."""

from __future__ import annotations

import shutil
import tomllib
from typing import TYPE_CHECKING

from blueprint import init

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from blueprint.testing import Repo

_PYPROJECT = '[project]\nname = "x"\nversion = "0"\nrequires-python = ">=3.12"\n'


def _python_repo(repo: Repo) -> None:
    repo.write("pyproject.toml", _PYPROJECT)
    repo.write("uv.lock", "")


def _init(repo: Repo, capsys: pytest.CaptureFixture[str], *, hooks: bool = False) -> tuple[int, str]:
    code = init.run(repo.root, hooks=hooks, beads=False, env=repo.env)
    return code, capsys.readouterr().out


def test_detect_names_the_stacks_and_the_files_it_read_before_anything_is_written(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python_repo(repo)
    _, out = _init(repo, capsys)
    assert "detect: python-uv (pyproject.toml, uv.lock)" in out
    assert out.index("detect:") < out.index("audit:") < out.index("plan:") < out.index("apply:")


def test_it_writes_what_is_missing_and_a_second_run_writes_nothing(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python_repo(repo)
    _init(repo, capsys)
    assert (repo.root / ".blueprint/base.just").is_file()
    assert "import '.blueprint/base.just'" in (repo.root / "justfile").read_text()
    before = {p: p.read_bytes() for p in repo.root.rglob("*") if p.is_file() and ".git/" not in p.as_posix()}
    _, out = _init(repo, capsys)
    assert "apply: nothing to write" in out
    assert before == {p: p.read_bytes() for p in repo.root.rglob("*") if p.is_file() and ".git/" not in p.as_posix()}


def test_the_preset_tables_are_added_to_pyproject_and_it_stays_valid_toml(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python_repo(repo)
    _init(repo, capsys)
    data = tomllib.loads((repo.root / "pyproject.toml").read_text())
    assert "select" in data["tool"]["ruff"]["lint"]
    assert data["tool"]["pyrefly"]["errors"]
    assert data["tool"]["shelf-size"]
    assert data["project"]["name"] == "x"


def test_an_existing_ruff_file_and_pyrefly_file_are_never_overwritten_or_shadowed(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python_repo(repo)
    repo.write("ruff.toml", '[lint]\nselect = ["E"]\n')
    repo.write("pyrefly.toml", "# mine\n")
    _init(repo, capsys)
    assert (repo.root / "ruff.toml").read_text() == '[lint]\nselect = ["E"]\n'
    assert (repo.root / "pyrefly.toml").read_text() == "# mine\n"
    data = tomllib.loads((repo.root / "pyproject.toml").read_text())
    assert "ruff" not in data.get("tool", {})
    assert "pyrefly" not in data.get("tool", {})


def test_an_existing_pyproject_table_is_kept_exactly_as_written(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    mine = _PYPROJECT + '\n[tool.ruff.lint]\nselect = ["E", "F"]  # my own\n'
    repo.write("pyproject.toml", mine)
    repo.write("uv.lock", "")
    _init(repo, capsys)
    text = (repo.root / "pyproject.toml").read_text()
    assert text.startswith(mine)
    assert tomllib.loads(text)["tool"]["ruff"]["lint"]["select"] == ["E", "F"]


def test_an_existing_justfile_keeps_its_recipes(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python_repo(repo)
    repo.write("justfile", "mine:\n    echo mine\n")
    _init(repo, capsys)
    assert "mine:\n    echo mine\n" in (repo.root / "justfile").read_text()


def test_no_hooks_installs_no_hook_and_writes_no_hook_config(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python_repo(repo)
    repo.fake_tool(repo.bin_dir / "prek", "ran")
    (repo.bin_dir / "prek").write_text(f'#!/bin/sh\necho "$@" >> "{repo.bin_dir}/prek.calls"\n')
    _, out = _init(repo, capsys, hooks=False)
    assert not (repo.root / ".pre-commit-config.yaml").exists()
    assert not (repo.bin_dir / "prek.calls").exists()
    assert "hooks" in out.split("left:")[1]


def test_hooks_write_the_config_and_run_prek_install(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python_repo(repo)
    repo.fake_tool(repo.bin_dir / "prek", "ran")
    (repo.bin_dir / "prek").write_text(f'#!/bin/sh\necho "$@" >> "{repo.bin_dir}/prek.calls"\n')
    _init(repo, capsys, hooks=True)
    assert "gate" in (repo.root / ".pre-commit-config.yaml").read_text()
    assert (repo.bin_dir / "prek.calls").read_text().startswith("install")


def test_an_existing_hook_config_is_kept(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python_repo(repo)
    repo.write(".pre-commit-config.yaml", "repos: []\n")
    _init(repo, capsys, hooks=True)
    assert (repo.root / ".pre-commit-config.yaml").read_text() == "repos: []\n"


def test_the_output_ends_with_the_rows_it_could_not_set_up(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python_repo(repo)
    code, out = _init(repo, capsys)
    tail = out.split("left:")[1]
    assert code == 1
    assert "stack.python-uv.python-pin" in tail  # no .python-version: the owner picks the version
    assert out.rstrip().endswith(tail.rstrip())


def test_a_detected_stack_with_no_profile_is_an_error(
    repo: Repo, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _python_repo(repo)
    monkeypatch.setattr(init, "_profiled", lambda _stack: False)
    code = init.run(repo.root, hooks=False, beads=False, env=repo.env)
    assert code == 2
    assert "python-uv has no profile" in capsys.readouterr().err
    assert not (repo.root / "justfile").exists()


def test_a_repo_with_no_detectable_stack_is_an_error_that_writes_nothing(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    repo.write("notes.txt", "hello\n")
    code = init.run(repo.root, hooks=False, beads=False, env=repo.env)
    assert code == 2
    assert "no stack" in capsys.readouterr().err
    assert not (repo.root / "docs").exists()


def test_it_runs_from_the_installed_package_with_no_shelf_clone(tmp_path: Path) -> None:
    import inspect  # noqa: PLC0415

    source = inspect.getsource(init)
    assert "tools/onboard" not in source
    assert "SHELF_HOME" not in source


def _fake(repo: Repo, name: str, version_out: str, log: bool = True) -> None:
    calls = repo.bin_dir / f"{name}.calls"
    body = f'#!/bin/sh\necho "$@" >> "{calls}"\n' if log else "#!/bin/sh\n"
    (repo.bin_dir / name).write_text(body + f'case "$1" in --version|version) echo "{version_out}";; esac\n')
    (repo.bin_dir / name).chmod(0o755)


def test_beads_is_suggested_not_demanded_and_not_a_left_row(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python_repo(repo)
    _, out = _init(repo, capsys)
    suggested = out.split("suggested:")[1]
    assert "blueprint init --beads" in suggested
    assert "backlog" not in out.split("left:")[1].split("suggested:")[0]


def test_the_suggestions_name_the_shelf_catalog(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python_repo(repo)
    _, out = _init(repo, capsys)
    assert "catalog" in out.split("suggested:")[1]


def test_beads_opt_in_runs_bd_init_without_hooks_and_the_suggestion_goes(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python_repo(repo)
    _fake(repo, "bd", "bd version 1.3.1 (abc)")
    code = init.run(repo.root, hooks=False, beads=True, env=repo.env)
    out = capsys.readouterr().out
    assert (repo.bin_dir / "bd.calls").read_text().splitlines()[0] == "init --skip-hooks"
    assert "blueprint init --beads" not in out
    assert code in {0, 1}


def test_without_the_flag_bd_is_never_run(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python_repo(repo)
    _fake(repo, "bd", "bd version 1.3.1 (abc)")
    _init(repo, capsys)
    assert not (repo.bin_dir / "bd.calls").exists()


def test_mise_toml_is_written_from_the_versions_of_the_tools_on_path(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python_repo(repo)
    _fake(repo, "uv", "uv 0.13.0 (abc 2026-01-01)")
    _fake(repo, "mise", "2026.1.1")
    _init(repo, capsys)
    data = tomllib.loads((repo.root / "mise.toml").read_text())
    assert data["tools"]["uv"] == "0.13.0"
    assert (repo.bin_dir / "mise.calls").read_text().splitlines()[-1] == "lock"


def test_an_existing_mise_toml_is_kept(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python_repo(repo)
    repo.write("mise.toml", '[tools]\nuv = "0.9.0"\n')
    _fake(repo, "uv", "uv 0.13.0 (abc)")
    _init(repo, capsys)
    assert (repo.root / "mise.toml").read_text() == '[tools]\nuv = "0.9.0"\n'


def test_a_tool_whose_version_cannot_be_read_stays_a_left_row(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    _python_repo(repo)
    (repo.bin_dir / "git").symlink_to(shutil.which("git") or "git")
    repo.env["PATH"] = str(repo.bin_dir)
    _, out = _init(repo, capsys)
    assert not (repo.root / "mise.toml").exists()
    assert "stack.tool-pins" in out.split("left:")[1]
