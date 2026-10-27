"""RealGit's memo and fetch retry, with the git runner replaced: no git process starts here."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from git_porcelain import Git, GitError, RealGit, RemoteError
from git_porcelain import real as real_module
from git_porcelain.testing import FakeGit

if TYPE_CHECKING:
    from collections.abc import Callable


class Runner:
    """A stand-in for ``run_git`` that answers by subcommand and counts calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.answers: dict[str, str] = {
            "--git-common-dir": "/repo/.git\n",
            "--show-toplevel": "/repo\n",
            "--is-inside-work-tree": "true\n",
            "get-url": "git@example.invalid:o.git\n",
            "--get": "value\n",
            "symbolic-ref": "main\n",
        }
        self.failures: list[GitError] = []

    def __call__(self, vault: Path, *args: str, **_: object) -> str:
        self.calls.append(args)
        if self.failures and args[0] == "fetch":
            raise self.failures.pop(0)
        for marker, answer in self.answers.items():
            if marker in args:
                return answer
        return ""

    def count(self, marker: str) -> int:
        return sum(marker in call for call in self.calls)


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch) -> Runner:
    fake = Runner()
    monkeypatch.setattr(real_module, "run_git", fake)
    return fake


def _asks(git: RealGit) -> Callable[[], None]:
    def ask() -> None:
        git.common_dir()
        git.toplevel()
        git.is_inside_work_tree()
        git.remote_url()
        git.config_get("user.name")
        git.branch()

    return ask


def test_both_implementations_satisfy_the_protocol() -> None:
    real: Git = RealGit(Path("/somewhere"))
    fake: Git = FakeGit.init(Path("/virtual"))
    assert real.path == Path("/somewhere")
    assert fake.path == Path("/virtual")


def test_read_only_answers_cost_one_git_process_each(runner: Runner) -> None:
    git = RealGit(Path("/repo"))
    for _ in range(30):
        _asks(git)()
    assert len(runner.calls) == 6
    assert git.common_dir() == Path("/repo/.git")
    assert git.branch() == "main"


def test_a_write_forgets_what_it_may_have_changed(runner: Runner) -> None:
    git = RealGit(Path("/repo"))
    git.branch()
    git.checkout("other")
    git.branch()
    assert runner.count("symbolic-ref") == 2


def test_invalidate_forgets_everything_for_every_view_of_the_repository(runner: Runner) -> None:
    git = RealGit(Path("/repo"))
    other = git.at(Path("/repo-w1"))
    git.toplevel()
    other.toplevel()
    other.invalidate()
    git.toplevel()
    other.toplevel()
    assert runner.count("--show-toplevel") == 4


def test_a_view_keeps_its_own_answers(runner: Runner) -> None:
    git = RealGit(Path("/repo"))
    git.at(Path("/repo-w1")).toplevel()
    git.toplevel()
    assert runner.count("--show-toplevel") == 2


def test_memoize_off_asks_every_time(runner: Runner) -> None:
    git = RealGit(Path("/repo"), memoize=False)
    git.toplevel()
    git.toplevel()
    assert runner.count("--show-toplevel") == 2


def test_a_missing_answer_is_memoized_too(runner: Runner) -> None:
    runner.answers["--get"] = ""
    git = RealGit(Path("/repo"))
    assert git.config_get("demo.key") is None
    assert git.config_get("demo.key") is None
    assert runner.count("--get") == 1


def test_fetch_tries_again_when_it_loses_a_ref_lock(runner: Runner) -> None:
    runner.failures = [GitError("git fetch exited 1: cannot lock ref 'refs/remotes/origin/main'")] * 2
    waits: list[float] = []
    RealGit(Path("/repo"), sleep=waits.append).fetch()
    assert runner.count("fetch") == 3
    assert waits == [0.1, 0.2]


def test_fetch_gives_up_on_any_other_failure(runner: Runner) -> None:
    runner.failures = [GitError("git fetch exited 128: Could not resolve host: example.invalid")]
    with pytest.raises(RemoteError) as caught:
        RealGit(Path("/repo"), sleep=lambda _: None).fetch()
    assert caught.value.reason == "offline"
    assert runner.count("fetch") == 1


def test_the_env_reaches_every_call_including_status_and_unmerged(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[object] = []

    def fake_run(vault: Path, *args: str, **kwargs: object) -> str:
        seen.append(kwargs.get("env"))
        return ""

    monkeypatch.setattr(real_module, "run_git", fake_run)
    monkeypatch.setattr("git_porcelain.porcelain.run_git", fake_run)
    git = RealGit(Path("/repo"), env={"GIT_DIR": "/pinned"})
    git.status()
    git.unmerged()
    git.toplevel()
    assert seen == [{"GIT_DIR": "/pinned"}] * 3
