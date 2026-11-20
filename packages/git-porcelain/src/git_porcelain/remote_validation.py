"""Shared real/fake validation before remote commands can have side effects."""

from __future__ import annotations


def validate_remote(remote: str | None) -> None:
    if remote is not None and remote.startswith("-"):
        msg = "remote must not start with '-'"
        raise ValueError(msg)


def validate_delete_ref(ref: str) -> None:
    if not ref.startswith("refs/"):
        msg = "remote deletion requires a full refs/ name"
        raise ValueError(msg)
