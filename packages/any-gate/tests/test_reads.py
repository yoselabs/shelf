"""any_gate.reads: the soundness check of step inputs. A step that reads a file its globs omit is skipped when that file changes:
the check compares what a step read (python audit hook) with what it declares, and says "cannot judge" rather than green when it ran
something it cannot see."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING

import pytest
from any_gate import opens, reads

if TYPE_CHECKING:
    from pathlib import Path

TRACKED = frozenset({"src/a.py", "src/b.py", "config/rules.toml", "docs/readme.md"})


def _trace(read: set[str], *, dirs: set[str] | None = None, opaque: tuple[str, ...] = (), pythons: int = 1) -> reads.Trace:
    return reads.Trace(frozenset(read), frozenset(dirs or ()), opaque, pythons)


def test_a_read_outside_the_declared_globs_is_under_declared() -> None:
    got = reads.judge("lint", ["src/*"], TRACKED, _trace({"src/a.py", "config/rules.toml"}), ())
    assert got.status == "UNDER"
    assert got.under == ("config/rules.toml",)


def test_every_read_declared_and_nothing_opaque_is_sound() -> None:
    got = reads.judge("lint", ["src/*", "config/*"], TRACKED, _trace({"src/a.py", "config/rules.toml"}), ())
    assert got.status == "SOUND"
    assert got.under == ()


def test_an_opaque_command_makes_a_clean_trace_cannot_judge_never_green() -> None:
    got = reads.judge("lint", ["src/*"], TRACKED, _trace({"src/a.py"}, opaque=("ruff",)), ())
    assert got.status == "CANNOT"
    assert "ruff" in got.why


def test_a_recipe_the_static_scan_calls_opaque_is_cannot_judge() -> None:
    got = reads.judge("lint", ["src/*"], TRACKED, _trace({"src/a.py"}), ("uv",))
    assert got.status == "CANNOT"
    assert "uv" in got.why


def test_a_proven_read_wins_over_opacity() -> None:
    got = reads.judge("lint", ["src/*"], TRACKED, _trace({"config/rules.toml"}, opaque=("ruff",)), ())
    assert got.status == "UNDER"


def test_no_python_process_reporting_is_cannot_judge() -> None:
    got = reads.judge("lint", ["src/*"], TRACKED, _trace(set(), pythons=0), ())
    assert got.status == "CANNOT"


def test_a_step_that_declares_everything_is_sound_by_construction() -> None:
    got = reads.judge("test", ["*"], TRACKED, _trace({"config/rules.toml"}, opaque=("uv",)), ("uv",))
    assert got.status == "WHOLE"


def test_the_gate_definition_files_are_covered_by_the_run_everything_rule() -> None:
    tracked = TRACKED | {"justfile", ".blueprint/base.just", "gate-inputs.toml"}
    got = reads.judge("lint", ["src/*"], tracked, _trace({"src/a.py", "justfile", ".blueprint/base.just"}), ())
    assert got.status == "SOUND"


def test_listing_a_folder_none_of_whose_files_is_declared_is_under_declared() -> None:
    got = reads.judge("lint", ["src/*"], TRACKED, _trace({"src/a.py"}, dirs={"config"}), ())
    assert got.status == "UNDER"
    assert got.under == ("config/ (listed)",)


def test_listing_a_folder_with_a_declared_file_is_covered() -> None:
    got = reads.judge("lint", ["src/*"], TRACKED, _trace({"src/a.py"}, dirs={"src"}), ())
    assert got.status == "SOUND"


def test_a_glob_matching_no_read_file_is_reported_as_wide_information_only() -> None:
    got = reads.judge("lint", ["src/*", "docs/*"], TRACKED, _trace({"src/a.py"}), ())
    assert got.status == "SOUND"
    assert got.wide == ("docs/*",)


def test_wide_is_not_claimed_when_the_view_is_incomplete() -> None:
    got = reads.judge("lint", ["src/*", "docs/*"], TRACKED, _trace({"src/a.py"}, opaque=("ruff",)), ())
    assert got.wide == ()


def _recipe(*lines: str, shebang: bool = False, deps: tuple[str, ...] = ()) -> dict[str, object]:
    return {"body": [[line] for line in lines], "shebang": shebang, "dependencies": [{"recipe": d} for d in deps]}


def test_static_scan_accepts_plain_python_and_names_everything_else() -> None:
    dump = {
        "a": _recipe("python scripts/x.py --flag"),
        "b": _recipe("python3 -I tools/y.py"),
        "c": _recipe("uv run python -m x"),
        "d": _recipe("echo hi", "ruff check ."),
        "e": _recipe("#!/usr/bin/env bash", "echo", shebang=True),
        "f": _recipe("python x.py && shellcheck a.sh", deps=("a",)),
        "g": _recipe("python x.py", deps=("c",)),
    }
    assert reads.opaque_commands(dump, "a") == ()
    assert reads.opaque_commands(dump, "b") == ("python -I",)
    assert reads.opaque_commands(dump, "c") == ("uv",)
    assert reads.opaque_commands(dump, "d") == ("ruff",)
    assert reads.opaque_commands(dump, "e") == ("bash",)
    assert reads.opaque_commands(dump, "f") == ("shellcheck",)
    assert reads.opaque_commands(dump, "g") == ("uv",)  # a dependency's commands count


def test_an_unreadable_recipe_is_opaque() -> None:
    assert reads.opaque_commands({}, "lint") == ("recipe unreadable",)


# --- the whole thing, on fixture repos: a justfile whose step runs a python script that reads two files ---

needs_just = pytest.mark.skipif(shutil.which("just") is None, reason="just is not installed")


def _fixture(root: Path, inputs: str) -> None:
    """A repo whose step `lint` runs tools/lint.py, which reads src/a.py and config/rules.toml; `inputs` is its step-inputs.toml."""
    files = {
        "justfile": f"lint:\n    {sys.executable} tools/lint.py\n",
        "tools/lint.py": "from pathlib import Path\nPath('src/a.py').read_text()\nPath('config/rules.toml').read_text()\n",
        "src/a.py": "x = 1\n",
        "config/rules.toml": "a = 1\n",
        ".blueprint/step-inputs.toml": inputs,
    }
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]
    subprocess.run([*git, "init", "-q"], cwd=root, check=True)
    subprocess.run([*git, "add", "-A"], cwd=root, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "c"], cwd=root, check=True)


def _soundness(root: Path) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "GATE_READS_ROOT"}}
    return subprocess.run(
        [sys.executable, "-m", "any_gate", "steps", "--all", "--reads", "--gate-slots", "0", "lint"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


@needs_just
def test_the_under_declared_fixture_is_caught_naming_step_and_file(tmp_path: Path) -> None:
    _fixture(tmp_path, 'lint = ["src/*"]\n')
    done = _soundness(tmp_path)
    assert done.returncode == 1, done.stderr
    assert "UNDER lint" in done.stderr
    assert "config/rules.toml" in done.stderr
    assert "tools/lint.py" in done.stderr  # the script itself is an input too


@needs_just
def test_the_correct_fixture_passes_and_says_what_it_cannot_see(tmp_path: Path) -> None:
    _fixture(tmp_path, 'lint = ["src/*", "config/*", "tools/*", "docs/*"]\n')
    done = _soundness(tmp_path)
    assert done.returncode == 0, done.stderr
    assert "SOUND lint" in done.stderr
    assert "wide lint: docs/*" in done.stderr  # information only: the exit code stays 0
    assert "not seen:" in done.stderr


@needs_just
def test_a_step_running_something_opaque_is_cannot_judge_not_ok(tmp_path: Path) -> None:
    _fixture(tmp_path, 'lint = ["src/*", "config/*", "tools/*"]\n')
    (tmp_path / "justfile").write_text(f"lint:\n    {sys.executable} tools/lint.py\n    cat src/a.py > /dev/null\n")
    done = _soundness(tmp_path)
    assert done.returncode == 0, done.stderr
    assert "CANNOT lint" in done.stderr
    assert "SOUND lint" not in done.stderr


def test_the_hook_records_reads_and_spawns_only_inside_the_roots(tmp_path: Path) -> None:
    folder = opens.prepare(tmp_path / "hook")
    inside = tmp_path / "repo"
    inside.mkdir()
    (inside / "f.txt").write_text("x")
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env = opens.env_for("s", folder, env) | {"GATE_READS_ROOT": str(inside)}
    code = textwrap.dedent("""
        import os, subprocess, sys
        open(sys.argv[1] + '/f.txt').read()
        open('/etc/hosts').close()
        os.listdir(sys.argv[1])
        subprocess.run(['cat', '/dev/null'])
    """)
    subprocess.run([sys.executable, "-c", code, str(inside)], check=True, env=env, cwd=inside)
    trace = reads.load(folder, "s", inside)
    assert trace.reads == {"f.txt"}
    assert trace.dirs == frozenset({"."})
    assert trace.opaque == ("cat",)
    assert trace.pythons == 1


def test_the_import_systems_folder_listings_are_not_reads_of_the_folder(tmp_path: Path) -> None:
    folder = opens.prepare(tmp_path / "hook")
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "mod.py").write_text("X = 1\n")
    env = opens.env_for("s", folder, {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}) | {"GATE_READS_ROOT": str(repo)}
    code = "import sys; sys.path.insert(0, 'pkg'); import mod"
    subprocess.run([sys.executable, "-c", code], check=True, env=env, cwd=repo)
    trace = reads.load(folder, "s", repo)
    assert trace.dirs == frozenset()
    assert "pkg/mod.py" in trace.reads  # the module's file is a read: it is an input


def test_a_long_list_of_files_is_shown_as_the_folders_they_sit_in() -> None:
    files = (*(f"packages/x/src/m{i}.py" for i in range(30)), "config/rules.toml")
    text = reads.lines([reads.Verdict("lint", "UNDER", files)])[0]
    assert "31 files: 30 under packages/x/src" in text
    assert "config/rules.toml" in text


def _contract_repo(root: Path, inputs: str) -> None:
    """The a2kay-cydc shape: backend `test` validates contract/schema.json, but the default gives it only backend/*."""
    files = {
        "justfile": f"test:\n    {sys.executable} backend/tests/check_contract.py\n",
        "backend/tests/check_contract.py": (
            "from pathlib import Path\nPath('contract/schema.json').read_text()\nPath('backend/app.py').read_text()\n"
        ),
        "backend/app.py": "x = 1\n",
        "contract/schema.json": "{}\n",
        ".blueprint/step-inputs.toml": inputs,
    }
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]
    subprocess.run([*git, "init", "-q"], cwd=root, check=True)
    subprocess.run([*git, "add", "-A"], cwd=root, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "c"], cwd=root, check=True)


@needs_just
def test_a_backend_test_step_that_validates_contract_files_but_declares_only_backend_is_caught(tmp_path: Path) -> None:
    _contract_repo(tmp_path, 'test = ["backend/*"]\n')
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "GATE_READS_ROOT"}}
    cmd = [sys.executable, "-m", "any_gate", "steps", "--all", "--reads", "--gate-slots", "0", "test"]
    done = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, check=False, env=env)
    assert done.returncode == 1, done.stderr
    assert "UNDER test" in done.stderr
    assert "contract/schema.json" in done.stderr
    (tmp_path / ".blueprint/step-inputs.toml").write_text('test = ["backend/*", "contract/*"]\n')
    fixed = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, check=False, env=env)
    assert fixed.returncode == 0, fixed.stderr
    assert "SOUND test" in fixed.stderr
