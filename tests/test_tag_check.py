"""The pre-push tag check: a version on the released branch without its tag blocks, an allowance is explicit and never stale."""

import subprocess
from pathlib import Path

import pytest

from tools import tag_check

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false"]


def run(cwd: Path, *args: str) -> None:
    subprocess.run([*GIT, *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo whose `main` carries packages a 0.1.0 and b 0.2.0, with a bare remote named origin."""
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    for name, version in (("a", "0.1.0"), ("b", "0.2.0")):
        (work / "packages" / name).mkdir(parents=True)
        (work / "packages" / name / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "{version}"\n', encoding="utf-8")
    run(work, "add", "-A")
    run(work, "commit", "-qm", "init")
    run(work, "remote", "add", "origin", str(remote))
    run(work, "push", "-q", "origin", "main")
    return work


def check(repo: Path, allow: str = "") -> int:
    allow_file = repo / "allow.toml"
    allow_file.write_text(allow, encoding="utf-8")
    return tag_check.main(["--repo", str(repo), "--allow", str(allow_file)])


def tag(repo: Path, name: str) -> None:
    run(repo, "tag", name)
    run(repo, "push", "-q", "origin", name)


def test_untagged_versions_block_and_name_the_missing_tag(repo, capsys):
    assert check(repo) == 1
    err = capsys.readouterr().err
    assert "a 0.1.0: no tag a-v0.1.0" in err
    assert "b 0.2.0: no tag b-v0.2.0" in err


def test_a_pushed_tag_satisfies_its_package(repo, capsys):
    tag(repo, "a-v0.1.0")
    assert check(repo) == 1
    err = capsys.readouterr().err
    assert "a 0.1.0" not in err
    assert "b-v0.2.0" in err


def test_all_tagged_passes(repo):
    tag(repo, "a-v0.1.0")
    tag(repo, "b-v0.2.0")
    assert check(repo) == 0


def test_a_local_only_tag_does_not_count(repo, capsys):
    run(repo, "tag", "a-v0.1.0")
    run(repo, "tag", "b-v0.2.0")
    assert check(repo) == 1
    assert "no tag a-v0.1.0" in capsys.readouterr().err


def test_an_allowed_package_passes(repo):
    tag(repo, "a-v0.1.0")
    assert check(repo, '[allow]\nb = "candidate, never released"\n') == 0


def test_a_stale_allowance_fails(repo, capsys):
    tag(repo, "a-v0.1.0")
    tag(repo, "b-v0.2.0")
    assert check(repo, '[allow]\nb = "was pending"\nghost = "gone"\n') == 1
    err = capsys.readouterr().err
    assert "b 0.2.0 is tagged; delete its entry" in err
    assert "ghost is not a package" in err


def test_the_branch_checked_is_the_released_one_not_the_working_branch(repo):
    tag(repo, "a-v0.1.0")
    tag(repo, "b-v0.2.0")
    run(repo, "checkout", "-q", "-b", "feature")
    (repo / "packages" / "a" / "pyproject.toml").write_text('[project]\nname = "a"\nversion = "0.2.0"\n', encoding="utf-8")
    run(repo, "commit", "-qam", "bump on a feature branch")
    assert check(repo) == 0  # the bump is not released until it is on main


def test_no_released_branch_checks_nothing(tmp_path):
    empty = tmp_path / "empty"
    subprocess.run(["git", "init", "-q", "-b", "main", str(empty)], check=True)
    assert tag_check.main(["--repo", str(empty)]) == 0
