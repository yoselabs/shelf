"""Checkout command outcomes: refusals retain all diagnostics, spawn errors raise."""

from __future__ import annotations

from typing import TYPE_CHECKING

from git_porcelain import real_checkout, real_observe, real_write
from git_porcelain.api import DEFAULT_TIMEOUT, CommandResult
from git_porcelain.errors import GitTimeout

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from git_porcelain.api import Sha
    from git_porcelain.real import RealWorktree


def command(
    wt: RealWorktree,
    args: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    timed_out: str | None = None,
) -> CommandResult:
    try:
        done = wt.repo.try_run(wt.path, *args, env=env, timeout=timeout)
        return CommandResult(ok=done.rc == 0, output=done.output)
    except GitTimeout as exc:
        if exc.output:
            return CommandResult(ok=False, output=exc.output)
        if timed_out is not None and timeout == DEFAULT_TIMEOUT:
            return CommandResult(ok=False, output=timed_out)
        return CommandResult(ok=False, output=str(exc))
    finally:
        wt.repo.invalidate()


def rebase(wt: RealWorktree, base: str, *, update_refs: bool | None) -> CommandResult:
    target = real_checkout.resolve_commit(wt, base)
    config = [] if update_refs is None else ["-c", f"rebase.updateRefs={str(update_refs).lower()}"]
    return command(wt, [*config, "rebase", "-q", target])


def continue_rebase(wt: RealWorktree, *, missing_ok: bool) -> CommandResult:
    if missing_ok and not real_observe.rebasing(wt):
        return CommandResult(ok=True, output="")
    return command(wt, ["-c", "core.editor=true", "rebase", "--continue"])


def resolve_and_continue(wt: RealWorktree) -> CommandResult:
    files = real_observe.unmerged(wt)
    if any(real_write.has_markers(wt.path / path) for path in files):
        return CommandResult(ok=False, output="conflict markers remain")
    if files:
        done = wt.try_run("--literal-pathspecs", "add", "-A", "--pathspec-from-file=-", "--pathspec-file-nul", stdin="\0".join(files))
        wt.repo.invalidate()
        if done.rc:
            return CommandResult(ok=False, output=done.output)
    return command(wt, ["-c", "core.editor=true", "rebase", "--continue"])


def abort_rebase(wt: RealWorktree, *, missing_ok: bool, restore_to: Sha | None) -> CommandResult:
    target = real_checkout.resolve_commit(wt, str(restore_to)) if restore_to is not None else None
    result = CommandResult(ok=True, output="")
    if not missing_ok or real_observe.rebasing(wt):
        result = command(wt, ["rebase", "--abort"])
    if result.ok and target is not None:
        result = command(wt, ["reset", "--hard", target])
    return result
