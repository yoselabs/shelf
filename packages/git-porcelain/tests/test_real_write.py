"""Commit diagnostics distinguish hook refusals from git's own failures."""

from __future__ import annotations

import pytest

from git_porcelain import GitUnavailable, HookRejected
from git_porcelain.real_done import Done
from git_porcelain.real_write import record_failure


@pytest.mark.parametrize(
    "diagnostic",
    [
        (
            "error: Committing is not possible because you have unmerged files.\n"
            "hint: Fix them up.\nfatal: Exiting because of an unresolved conflict."
        ),
        "error: gpg failed to sign the data\nfatal: failed to write commit object",
        "fatal: empty ident name (for <>) not allowed",
        "Author identity unknown\nPlease tell me who you are.",
        "fatal: You have nothing to amend.",
        "fatal: cannot open COMMIT_EDITMSG: Permission denied",
        "error: unable to sign commit\nfatal: failed to write commit object",
        "error: cannot commit\nAdditional git diagnostic context",
        "On branch main\n\nChanges not staged for commit:\n  modified: a\nno changes added to commit",
    ],
)
@pytest.mark.parametrize("hooks", [False, True])
def test_git_commit_failures_are_never_hook_rejections(diagnostic: str, *, hooks: bool) -> None:
    with pytest.raises(GitUnavailable) as caught:
        record_failure(["commit"], Done(1, b"", diagnostic), hooks=hooks)
    assert caught.value.output == diagnostic
    assert diagnostic in str(caught.value)


@pytest.mark.parametrize("diagnostic", ["pre-commit refused", "hook declined", "hook failed", "hook rejected", "policy says no"])
@pytest.mark.parametrize("hooks", [False, True])
def test_hook_rejection_requires_positive_output(diagnostic: str, *, hooks: bool) -> None:
    if not hooks:
        with pytest.raises(GitUnavailable):
            record_failure(["commit"], Done(1, b"", diagnostic), hooks=hooks)
        return
    result = record_failure(["commit"], Done(1, b"", diagnostic), hooks=hooks)
    assert isinstance(result, HookRejected)
    assert result.output == diagnostic


def test_silent_commit_failure_has_no_positive_hook_match() -> None:
    with pytest.raises(GitUnavailable):
        record_failure(["commit"], Done(1, b"", ""), hooks=True)


def test_commit_failure_preserves_complete_stdout_and_stderr() -> None:
    stdout = "output\n" * 200
    stderr = "error: gpg failed to sign the data\n" + "detail\n" * 200
    with pytest.raises(GitUnavailable) as caught:
        record_failure(["commit"], Done(1, stdout.encode(), stderr), hooks=True)
    assert caught.value.output == (stdout + stderr).strip()
    assert caught.value.output in str(caught.value)
