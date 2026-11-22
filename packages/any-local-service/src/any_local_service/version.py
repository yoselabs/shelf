"""Build identity and attach-time skew, with build metadata supplied by the caller."""

from __future__ import annotations

import re

_LOCAL_RE = re.compile(r"\+(\d+)\.g[0-9a-f]+$", re.IGNORECASE)


class ServerVersionSkewError(RuntimeError):
    """A client is provably newer than the running server."""


def build_identity(base: str, *, count: int | None = None, commit: str | None = None) -> str:
    """Stamp a base version with a path-scoped commit count and SHA, when known."""
    if count is None and commit is None:
        return base
    if count is None or count < 0 or commit is None or re.fullmatch(r"[0-9a-f]+", commit, re.IGNORECASE) is None:
        message = "build identity needs a nonnegative commit count and hexadecimal commit"
        raise ValueError(message)
    return f"{base}+{count}.g{commit}"


def _commit_count(identity: str | None) -> int | None:
    match = _LOCAL_RE.search(identity) if identity else None
    return int(match.group(1)) if match else None


def check_attach_version(client_identity: str, server_identity: str | None) -> None:
    """Refuse a strictly newer client; equal, older and undecidable builds may attach."""
    client, server = _commit_count(client_identity), _commit_count(server_identity)
    if client is not None and server is not None and client > server:
        message = f"client {client_identity} is newer than server {server_identity}; restart the server before attaching"
        raise ServerVersionSkewError(message)
