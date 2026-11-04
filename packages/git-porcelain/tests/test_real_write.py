"""Commit diagnostics distinguish hook refusals from git's own failures."""

from __future__ import annotations

import pytest

from git_porcelain import GitUnavailable, HookRejected, Pushed, Sha
from git_porcelain.real_done import Done
from git_porcelain.real_remote import classify_push
from git_porcelain.real_write import record_failure


@pytest.mark.parametrize(
    ("rows", "hook", "kind"),
    [
        (b"", True, "HookRejected"),
        (b"!\tHEAD:refs/heads/main\t[remote rejected] (hook declined)\n", True, "RemoteRejected"),
        (b"!\tHEAD:refs/heads/main\t[rejected] (non-fast-forward)\n", False, "RefRejected"),
        (b"!\tHEAD:refs/heads/main\t[rejected] (fetch first)\n", False, "RefRejected"),
        (b"!\tHEAD:refs/heads/main\t[rejected] (stale info)\n", False, "RefRejected"),
        (b"!\tHEAD:refs/heads/main\t[rejected] (policy)\n", False, "RemoteRejected"),
        (
            b"=\tHEAD:refs/heads/one\t[up to date]\n!\tHEAD:refs/heads/main\t[rejected] (stale info)\n",
            False,
            "RemoteRejected",
        ),
    ],
)
@pytest.mark.parametrize("diagnostic", ["", "error: nope", "remote: rejected by a hook\n" + "detail\n" * 200])
def test_push_classification_uses_ref_rows_and_hook_evidence(rows: bytes, *, hook: bool, kind: str, diagnostic: str) -> None:
    done = Done(1, rows, diagnostic, hooks=("pre-push",) if hook else ())
    result = classify_push(done, Sha("a" * 40))
    assert type(result).__name__ == kind
    assert result.output == (rows.decode() + diagnostic).strip()
    assert not isinstance(result, Pushed)
    assert len(result.tail) <= 600


def test_failed_push_summary_alone_is_not_hook_evidence() -> None:
    done = Done(1, b"", "error: failed to push some refs\n" + "detail\n" * 200)
    with pytest.raises(GitUnavailable) as caught:
        classify_push(done, Sha("a" * 40))
    assert caught.value.output == done.err.strip()


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
