"""Shared real/fake validation before remote commands can have side effects."""

from __future__ import annotations

from typing import TYPE_CHECKING

from git_porcelain.errors import PushRefused

if TYPE_CHECKING:
    from collections.abc import Sequence

_REFUSED_OPTIONS = ("--force", "--delete", "--mirror", "--prune")


def validate_remote(remote: str | None) -> None:
    if remote is not None and remote.startswith("-"):
        msg = "remote must not start with '-'"
        raise ValueError(msg)


def validate_delete_ref(ref: str) -> None:
    if not ref.startswith("refs/"):
        msg = "remote deletion requires a full refs/ name"
        raise ValueError(msg)


def validate_push(remote: str | None, refspecs: Sequence[str], options: Sequence[str] = ()) -> None:
    """A push through ``push_refspecs`` / ``push_request`` neither forces nor deletes: refuse those forms, naming one."""
    validate_remote(remote)
    for spec in refspecs:
        if spec.startswith("+"):
            msg = f"push refused: {spec!r} forces; a push here never replaces a remote tip"
            raise PushRefused(msg)
        if spec.startswith(":"):
            msg = f"push refused: {spec!r} deletes a remote ref; use delete_remote_at"
            raise PushRefused(msg)
    for option in options:
        if option in {"-f", "-d"} or option.startswith(_REFUSED_OPTIONS):
            hint = "push_lease is the lease" if option.startswith("--force-with-lease") else "a push here never forces or deletes"
            msg = f"push refused: option {option!r}; {hint}"
            raise PushRefused(msg)
