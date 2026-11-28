"""Secret scan: staged, range and full modes over a real gitleaks; a finding names the file and rule, never the secret."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from blueprint import secret_scan
from blueprint.secret_scan import ScanError, scan_full, scan_range, scan_staged

if TYPE_CHECKING:
    from blueprint.testing import Repo

_LEAK = 'aws_key = "AKIAZ7VRSQ2WKNBTXPLM"\n'
_LEAK_TOO = 'other = "AKIAZ7VRSQ2WKNBTXPLN"\n'


def _branch(repo: Repo) -> None:
    """main holds one clean commit; `work` tracks it, so the range base is that commit."""
    repo.write("README.md", "hello\n")
    repo.commit()
    repo.git("branch", "base")
    repo.git("checkout", "-q", "-b", "work")
    repo.git("branch", "--set-upstream-to=base")


def test_a_clean_tree_has_no_findings_in_every_scan(repo: Repo) -> None:
    _branch(repo)
    repo.write("a.py", "x = 1\n")
    repo.git("add", "a.py")
    assert [scan(repo.root, env=repo.env) for scan in (scan_staged, scan_range, scan_full)] == [[], [], []]


def test_staged_mode_sees_the_index_and_nothing_older(repo: Repo) -> None:
    repo.write("old.py", _LEAK)
    repo.commit()
    repo.write("new.py", _LEAK_TOO)
    repo.git("add", "new.py")
    found = scan_staged(repo.root, env=repo.env)
    assert [(f.file, f.rule) for f in found] == [("new.py", "aws-access-token")]


def test_range_mode_sees_commits_since_the_upstream_base(repo: Repo) -> None:
    _branch(repo)
    repo.write("leak.py", _LEAK)
    repo.commit()
    assert [f.file for f in scan_range(repo.root, env=repo.env)] == ["leak.py"]


def test_range_mode_skips_history_the_base_already_holds(repo: Repo) -> None:
    repo.write("old.py", _LEAK)
    repo.commit()
    repo.git("branch", "base")
    repo.git("checkout", "-q", "-b", "work")
    repo.git("branch", "--set-upstream-to=base")
    repo.write("fine.py", "x = 1\n")
    repo.commit()
    assert scan_range(repo.root, env=repo.env) == []
    assert [f.file for f in scan_full(repo.root, env=repo.env)] == ["old.py"]


@pytest.mark.parametrize("stage", ["staged", "unstaged", "untracked"])
def test_range_mode_sees_uncommitted_work(repo: Repo, stage: str) -> None:
    _branch(repo)
    if stage == "unstaged":
        repo.write("README.md", "hello\n" + _LEAK)
    else:
        repo.write("new.py", _LEAK)
        if stage == "staged":
            repo.git("add", "new.py")
    found = scan_range(repo.root, env=repo.env)
    assert [f.rule for f in found] == ["aws-access-token"]


def test_range_mode_without_an_upstream_scans_everything(repo: Repo) -> None:
    repo.write("leak.py", _LEAK)
    repo.commit()
    assert [f.file for f in scan_range(repo.root, env=repo.env)] == ["leak.py"]


def _two_unpushed_branches(repo: Repo) -> None:
    """main holds one clean commit; `other` (a sibling worktree's branch) holds a leak; `work` has no upstream."""
    repo.write("README.md", "hello\n")
    repo.commit()
    repo.git("checkout", "-q", "-b", "other")
    repo.write("other_leak.py", _LEAK)
    repo.commit()
    repo.git("checkout", "-q", "main")
    repo.git("checkout", "-q", "-b", "work")


def test_range_mode_without_an_upstream_ignores_another_branchs_leak(repo: Repo) -> None:
    _two_unpushed_branches(repo)
    repo.write("fine.py", "x = 1\n")
    repo.commit()
    assert scan_range(repo.root, env=repo.env) == []
    assert [f.file for f in scan_full(repo.root, env=repo.env)] == ["other_leak.py"]


def test_range_mode_without_an_upstream_still_sees_this_branchs_leak(repo: Repo) -> None:
    _two_unpushed_branches(repo)
    repo.write("leak.py", _LEAK_TOO)
    repo.commit()
    assert [f.file for f in scan_range(repo.root, env=repo.env)] == ["leak.py"]


def test_range_mode_on_the_default_branch_without_an_upstream_scans_its_own_history_only(repo: Repo) -> None:
    repo.write("old.py", _LEAK)
    repo.commit()
    repo.git("branch", "other")
    repo.git("checkout", "-q", "other")
    repo.write("other_leak.py", _LEAK_TOO)
    repo.commit()
    repo.git("checkout", "-q", "main")
    assert [f.file for f in scan_range(repo.root, env=repo.env)] == ["old.py"]


def test_a_finding_never_carries_the_secret(repo: Repo) -> None:
    repo.write("leak.py", _LEAK)
    repo.commit()
    (finding,) = scan_full(repo.root, env=repo.env)
    assert "AKIAZ7VRSQ2WKNBTXPLM" not in repr(finding)
    assert finding.line == 1


def test_a_missing_scanner_is_an_error_not_a_pass(repo: Repo) -> None:
    repo.write("a.py", "x = 1\n")
    repo.commit()
    env = {**repo.env, "PATH": str(repo.bin_dir)}
    with pytest.raises(ScanError, match="gitleaks"):
        scan_full(repo.root, env=env)


def test_help_exits_zero_and_an_unknown_flag_exits_two() -> None:
    run = lambda *a: subprocess.run([sys.executable, "-m", "blueprint.secret_scan", *a], capture_output=True, text=True, check=False)  # noqa: E731
    helped = run("--help")
    assert helped.returncode == 0
    assert "staged" in helped.stdout
    assert run("--bogus").returncode == 2


def test_the_command_line_exits_one_on_a_finding_and_zero_when_clean(repo: Repo) -> None:
    repo.write("a.py", "x = 1\n")
    repo.commit()
    cmd = [sys.executable, "-m", "blueprint.secret_scan", "full", "--repo", str(repo.root)]
    assert subprocess.run(cmd, env=repo.env, capture_output=True, check=False).returncode == 0
    repo.write("leak.py", _LEAK)
    repo.commit()
    done = subprocess.run(cmd, env=repo.env, capture_output=True, text=True, check=False)
    assert done.returncode == 1
    assert "leak.py:1 aws-access-token" in done.stderr
    assert "AKIAZ7VRSQ2WKNBTXPLM" not in done.stderr


def test_untracked_files_are_scanned_in_one_process_and_named_by_their_own_path(repo: Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    _branch(repo)
    for name in ("a.py", "b.py", "sub/c.py"):
        repo.write(name, "x = 1\n")
    repo.write("sub/leaky.py", _LEAK)
    starts: list[list[str]] = []
    real = secret_scan._exec
    monkeypatch.setattr(secret_scan, "_exec", lambda argv, *rest: (starts.append(list(argv)), real(argv, *rest))[1])
    found = scan_range(repo.root, env=repo.env)
    assert [(f.file, f.rule) for f in found] == [("sub/leaky.py", "aws-access-token")]
    assert sum(1 for argv in starts if argv[0] == "gitleaks" and "dir" in argv) == 1
