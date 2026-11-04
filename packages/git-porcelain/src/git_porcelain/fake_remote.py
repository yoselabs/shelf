"""In-memory explicit remote refs, leases and scoped fetches."""

from __future__ import annotations

from typing import TYPE_CHECKING

from git_porcelain import fake_flow
from git_porcelain.api import CommandResult, Pushed, RefRejected, RemoteRejected, Sha, Transient
from git_porcelain.errors import GitReadFailure, GitUnavailable, MissingRemote
from git_porcelain.fake_store import ancestors

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from git_porcelain.api import PushResult
    from git_porcelain.fake_store import CheckoutState, RepoState


def _source(state: RepoState, remote: str) -> tuple[str, RepoState]:
    name = next((key for key, url in state.remotes.items() if url == remote), remote)
    there = fake_flow.remote_state(state, name)
    if isinstance(there, str):
        raise GitUnavailable(there)
    return name, there


def remote_url(state: RepoState, remote: str) -> str:
    if remote not in state.remotes:
        msg = f"error: No such remote '{remote}'"
        raise MissingRemote(msg)
    url = state.remotes[remote]
    matches = [
        (value, key[4:-10])
        for key, value in state.config.items()
        if key.startswith("url.") and key.endswith(".insteadof") and url.startswith(value)
    ]
    if matches:
        prefix, replacement = max(matches, key=lambda pair: len(pair[0]))
        return replacement + url[len(prefix) :]
    return url


def fetch(state: RepoState, remote: str, refspecs: Sequence[str]) -> None:
    name, there = _source(state, remote)
    state.store.absorb(there.store)
    if not refspecs:
        fake_flow.fetch(state, name)
        tip = there.refs.get(f"refs/heads/{there.default_branch}")
        if tip:
            state.refs["FETCH_HEAD"] = tip
        return
    for index, spec in enumerate(refspecs):
        src, colon, dst = spec.removeprefix("+").partition(":")
        ref = src if src in there.refs else f"refs/heads/{src}"
        sha = there.refs.get(ref, src if src in there.store.commits else None)
        if sha is None:
            msg = f"fatal: couldn't find remote ref {src}"
            raise GitUnavailable(msg)
        if index == 0:
            state.refs["FETCH_HEAD"] = sha
        if colon:
            state.refs[dst] = sha
        if ref.startswith("refs/heads/") and remote in state.remotes:
            state.refs[f"refs/remotes/{name}/{ref.removeprefix('refs/heads/')}"] = sha


def delete_remote_at(state: RepoState, remote: str, ref: str, expected: Sha) -> None:
    try:
        name, there = _source(state, remote)
    except GitUnavailable as exc:
        msg = f"cannot verify remote deletion: {exc}"
        raise GitReadFailure(msg) from exc
    old = there.refs.get(ref)
    if old is None:
        return
    if old != expected:
        msg = "[rejected] (stale info)"
        raise GitUnavailable(msg)
    refusal = fake_flow.hook_refusal(state, {})
    if refusal:
        raise GitUnavailable(refusal.tail)
    del there.refs[ref]
    if remote in state.remotes and ref.startswith("refs/heads/"):
        state.refs.pop(f"refs/remotes/{name}/{ref.removeprefix('refs/heads/')}", None)


def _push_specs(state: RepoState, checkout: CheckoutState, name: str, refspecs: Sequence[str]) -> list[str]:
    if refspecs:
        return list(refspecs)
    branch = (checkout.head_ref or "").removeprefix("refs/heads/")
    configured = state.config.get(f"remote.{name}.push")
    if configured:
        return [configured]
    if state.config.get("push.default", "simple") not in {"simple", "upstream"}:
        msg = "fake push does not model this configured push.default mode"
        raise GitUnavailable(msg)
    if state.config.get(f"branch.{branch}.remote") == name:
        return [f"HEAD:{state.config.get(f'branch.{branch}.merge', checkout.head_ref or '')}"]
    msg = "fatal: The current branch has no upstream branch."
    raise GitUnavailable(msg)


def _resolve_push(
    state: RepoState, checkout: CheckoutState, spec: str, captured: str | None, *, options: Sequence[str]
) -> tuple[str, str | None]:
    src, colon, dst = spec.removeprefix("+").partition(":")
    if not colon:
        dst = checkout.head_ref if src == "HEAD" else src
    if not dst:
        msg = "push needs an explicit destination for detached HEAD"
        raise GitUnavailable(msg)
    if not dst.startswith("refs/"):
        dst = f"refs/heads/{dst}"
    if "--delete" in options or "-d" in options:
        src = ""
    sha = captured if src == "HEAD" else state.commit_named(src, checkout) if src else None
    if src and sha is None:
        msg = f"error: src refspec {src} does not match any"
        raise GitUnavailable(msg)
    return dst, sha


def _check_push(
    state: RepoState,
    there: RepoState,
    name: str,
    dst: str,
    sha: str | None,
    *,
    force: bool,
    options: Sequence[str],
) -> RefRejected | RemoteRejected | None:
    old = there.refs.get(dst)
    if "--force-with-lease" in options:
        expected = state.refs.get(f"refs/remotes/{name}/{dst.removeprefix('refs/heads/')}")
        if old != expected:
            return RefRejected("[rejected] (stale info)")
        force = True
    if old is not None and sha is not None:
        if not force and old not in ancestors(state.store, sha):
            return RefRejected("[rejected] (non-fast-forward)")
        if (
            "--dry-run" not in options
            and there.config.get("receive.denynonfastforwards") == "true"
            and old not in ancestors(state.store, sha)
        ):
            return RemoteRejected("[remote rejected] (non-fast-forward)")
    return None


def _apply_push(state: RepoState, there: RepoState, name: str, dst: str, sha: str | None) -> None:
    there.store.absorb(state.store)
    if sha is None:
        there.refs.pop(dst, None)
    else:
        there.refs[dst] = sha
    if dst.startswith("refs/heads/"):
        tracking = f"refs/remotes/{name}/{dst.removeprefix('refs/heads/')}"
        if sha is None:
            state.refs.pop(tracking, None)
        else:
            state.refs[tracking] = sha


def push_refspecs(
    state: RepoState,
    checkout: CheckoutState,
    remote: str,
    refspecs: Sequence[str],
    *,
    hook_env: Mapping[str, str] | None,
    options: Sequence[str] = (),
) -> PushResult:
    refusal = fake_flow.hook_refusal(state, hook_env or {})
    if refusal:
        return refusal
    try:
        name, there = _source(state, remote)
    except GitUnavailable as exc:
        return Transient(str(exc))
    if any(opt not in {"--force-with-lease", "--force", "-f", "--dry-run", "--delete", "-d"} for opt in options):
        msg = "fake push does not model these push options"
        raise GitUnavailable(msg)
    specs = _push_specs(state, checkout, name, refspecs)
    captured = state.head_sha(checkout)
    result_sha: str | None = None
    for spec in specs:
        force = spec.startswith("+") or "--force" in options or "-f" in options
        dst, sha = _resolve_push(state, checkout, spec, captured, options=options)
        rejected = _check_push(state, there, name, dst, sha, force=force, options=options)
        if rejected is not None:
            return rejected
        if "--dry-run" not in options:
            _apply_push(state, there, name, dst, sha)
            if sha is not None and result_sha is None:
                result_sha = sha
    return Pushed(Sha(result_sha or ""))


def push_request(
    state: RepoState,
    checkout: CheckoutState,
    remote: str | None,
    refspecs: Sequence[str],
    *,
    options: Sequence[str],
    hook_env: Mapping[str, str] | None,
) -> CommandResult:
    branch = (checkout.head_ref or "").removeprefix("refs/heads/")
    name = (
        remote
        or state.config.get(f"branch.{branch}.pushremote")
        or state.config.get("remote.pushdefault")
        or state.config.get(f"branch.{branch}.remote", "origin")
    )
    try:
        result = push_refspecs(state, checkout, name, refspecs, hook_env=hook_env, options=options)
    except GitUnavailable as exc:
        return CommandResult(ok=False, output=str(exc))
    return CommandResult(ok=isinstance(result, Pushed), output="" if isinstance(result, Pushed) else result.tail)
