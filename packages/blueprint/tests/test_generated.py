"""The "generated file is current" step: a generator writes into a temp folder, and what it wrote must equal the committed files.

A repo declares each generated output in `[[tool.blueprint.gate.generated]]` (name, command with `{out}`, outputs, reads); blueprint renders
one `generated-<name>` step per entry and runs it as `python -m blueprint.generated <name>`. a2kay's `contract-check` and
`ui-css-check` are two entries.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tomllib
from typing import TYPE_CHECKING

import pytest
from blueprint import generated as check_generated
from blueprint import render

if TYPE_CHECKING:
    from pathlib import Path

    from blueprint.testing import Repo

GENERATOR = """import pathlib, sys
out = pathlib.Path(sys.argv[1])
(out / "gen/sub").mkdir(parents=True, exist_ok=True)
(out / "gen/a.txt").write_text("A")
(out / "gen/sub/b.txt").write_text("B")
"""
WRITE = "python3 gen.py {out}"


def _repo(tmp_path: Path, *, command: str = WRITE, outputs: str = '["gen"]', extra: str = "") -> Path:
    """A repo whose generator (`gen.py`) writes `gen/a.txt` and `gen/sub/b.txt` under the output root, as the repo has them."""
    (tmp_path / "gen.py").write_text(GENERATOR)
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "x"\n[[tool.blueprint.gate.generated]]\nname = "gen"\ncommand = "{command}"\noutputs = {outputs}\n{extra}'
    )
    return tmp_path


def _commit_outputs(root: Path) -> None:
    (root / "gen/sub").mkdir(parents=True, exist_ok=True)
    (root / "gen/a.txt").write_text("A")
    (root / "gen/sub/b.txt").write_text("B")


def test_current_outputs_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _repo(tmp_path)
    _commit_outputs(root)
    assert check_generated.check(root, "gen") == 0
    assert "current" in capsys.readouterr().out


def test_a_changed_file_fails_and_is_named_with_the_regenerate_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _repo(tmp_path)
    _commit_outputs(root)
    (root / "gen/a.txt").write_text("stale")
    assert check_generated.check(root, "gen") == 1
    err = capsys.readouterr().err
    assert "gen/a.txt" in err
    assert "gen/sub/b.txt" not in err
    assert "regenerate" in err


def test_a_missing_file_and_an_extra_file_both_fail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _repo(tmp_path)
    _commit_outputs(root)
    (root / "gen/sub/b.txt").unlink()
    (root / "gen/old.txt").write_text("left behind")
    assert check_generated.check(root, "gen") == 1
    err = capsys.readouterr().err
    assert "gen/sub/b.txt: missing" in err
    assert "gen/old.txt: not generated" in err


def test_the_repo_is_not_touched_by_the_check(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "gen").mkdir()
    (root / "gen/a.txt").write_text("stale")
    check_generated.check(root, "gen")
    assert (root / "gen/a.txt").read_text() == "stale"
    assert not (root / "gen/sub").exists()


def test_a_generator_that_fails_is_exit_2_never_a_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _repo(tmp_path, command="python3 -c 'import sys; sys.exit(3)' {out}")
    assert check_generated.check(root, "gen") == 2
    assert "exited 3" in capsys.readouterr().err


def test_an_unknown_name_is_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _repo(tmp_path)
    assert check_generated.check(root, "nope") == 2
    assert "nope" in capsys.readouterr().err


def test_a_single_file_output_is_compared_too(tmp_path: Path) -> None:
    root = _repo(tmp_path, outputs='["gen/a.txt"]')
    (root / "gen").mkdir()
    (root / "gen/a.txt").write_text("A")
    assert check_generated.check(root, "gen") == 0
    (root / "gen/a.txt").write_text("B")
    assert check_generated.check(root, "gen") == 1


def test_the_module_runs_from_the_package(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _commit_outputs(root)
    done = subprocess.run(
        [sys.executable, "-I", "-m", "blueprint.generated", "--repo", str(root), "gen"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr


# --- rendering ---


def _declare(repo: Repo, reads: str = "") -> None:
    root = repo.root
    (root / "pyproject.toml").write_text(
        '[project]\nname = "x"\n[[tool.blueprint.gate.generated]]\nname = "css"\ncommand = "npm run css -- --out {out}"\n'
        f'outputs = ["ui/style.css"]\n{reads}[[tool.blueprint.gate.generated]]\nname = "contract"\n'
        'command = "uv run python s.py {out}"\noutputs = ["contract"]\n'
    )
    (root / "uv.lock").write_text("")


def test_each_entry_renders_a_step_that_runs_the_package_entry_point(repo: Repo) -> None:
    _declare(repo)
    parts = render.parts(repo.root)
    generated = parts[".blueprint/generated.just"]
    assert "\ngenerated-css:\n    uv run python -I -m blueprint.generated css" in generated
    assert "\ngenerated-contract:\n" in generated
    steps = re.findall(r'"([\w-]+)"', parts[".blueprint/base.just"].split("(steps ", 1)[1].split(")", 1)[0])
    assert {"generated-css", "generated-contract"} <= set(steps)


def test_a_repo_with_no_entries_renders_no_generated_part(repo: Repo) -> None:
    repo.write("pyproject.toml", '[project]\nname = "x"\n')
    assert ".blueprint/generated.just" not in render.parts(repo.root)


def test_the_default_inputs_are_the_outputs_and_the_declared_reads(repo: Repo) -> None:
    _declare(repo, reads='reads = ["ui/*", "tailwind.css"]\n')
    table = tomllib.loads(render.parts(repo.root)[render.INPUTS_PART])
    assert table["generated-css"] == ["ui/style.css", "ui/*", "tailwind.css", "*pyproject.toml"]
    assert table["generated-contract"] == ["*"]  # no `reads`: it may read anything, so it runs on any change


@pytest.mark.skipif(shutil.which("just") is None, reason="just is not installed")
def test_the_rendered_part_is_valid_just(repo: Repo) -> None:
    _declare(repo)
    render.write(repo.root)
    done = subprocess.run(["just", "--list"], cwd=repo.root, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    assert "generated-css" in done.stdout
    assert render.check(repo.root) == 0
