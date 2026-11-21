"""The stdlib-shadow gate step: a file or package named like a stdlib module, where a script run puts it on sys.path first, fails."""

import subprocess
from pathlib import Path

import pytest

from tools import stdlib_shadow


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    return tmp_path


def put(repo: Path, rel: str, text: str = "x = 1\n") -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def check(repo: Path, allow: str | None = None) -> int:
    allow_file = repo / "allow.toml"
    allow_file.write_text(allow or "", encoding="utf-8")
    return stdlib_shadow.main(["--repo", str(repo), "--allow", str(allow_file)])


def test_a_stdlib_named_file_in_scripts_fails_and_names_the_stdlib_module(repo, capsys):
    put(repo, "scripts/queue.py")
    assert check(repo) == 1
    err = capsys.readouterr().err
    assert "scripts/queue.py" in err
    assert "queue" in err


def test_the_same_name_inside_an_installed_package_passes(repo):
    put(repo, "src/mypkg/__init__.py")
    put(repo, "src/mypkg/queue.py")
    put(repo, "src/mypkg/profile/__init__.py")
    assert check(repo) == 0


def test_a_flat_module_directly_under_src_fails(repo):
    put(repo, "src/queue.py")
    assert check(repo) == 1


def test_a_top_level_package_named_like_stdlib_fails(repo, capsys):
    put(repo, "src/logging/__init__.py")
    assert check(repo) == 1
    assert "src/logging" in capsys.readouterr().err


def test_the_repo_root_is_a_script_directory(repo):
    put(repo, "profile.py")
    assert check(repo) == 1


def test_a_directory_is_a_script_directory_by_a_main_guard(repo):
    put(repo, "jobs/random.py")
    assert check(repo) == 0  # nothing there is run as a script
    put(repo, "jobs/run.py", 'if __name__ == "__main__":\n    pass\n')
    assert check(repo) == 1


def test_a_directory_is_a_script_directory_by_a_pep723_header(repo):
    put(repo, "jobs/run.py", "# /// script\n# dependencies = []\n# ///\n")
    put(repo, "jobs/string.py")
    assert check(repo) == 1


def test_a_dunder_main_module_is_not_a_shadow(repo):
    put(repo, "scripts/__main__.py")
    assert check(repo) == 0


def test_an_allowlisted_entry_passes(repo):
    put(repo, "scripts/queue.py")
    assert check(repo, '[allow]\n"scripts/queue.py" = "the job queue, run only as python -m"\n') == 0


def test_an_entry_without_a_reason_is_rejected(repo, capsys):
    put(repo, "scripts/queue.py")
    assert check(repo, '[allow]\n"scripts/queue.py" = ""\n') == 1
    assert "reason" in capsys.readouterr().err


def test_a_stale_entry_fails(repo, capsys):
    put(repo, "scripts/ok.py")
    assert check(repo, '[allow]\n"scripts/queue.py" = "was shadowing"\n') == 1
    assert "delete its entry" in capsys.readouterr().err


def test_a_clean_tree_passes(repo):
    put(repo, "scripts/build.py", 'if __name__ == "__main__":\n    pass\n')
    put(repo, "tools/check_things.py")
    assert check(repo) == 0
