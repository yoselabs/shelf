"""One ASGI middleware that gates every HTTP request on a header token.

Two ways to know a token sit behind the one gate:

- :class:`StaticTokenGate` — a static secret, compared in constant time; :func:`stable_token`
  mints it once to a ``0600`` file and reuses it, so a client recipe survives a restart.
- :class:`LeaseTokenGate` — a :class:`LeaseSet` of minted tokens, resolved on every request:
  no TTL, and a revoke fails the very next call.

Missing or refused → ``401`` with a JSON body. Non-HTTP scopes (``lifespan``,
``websocket``) pass straight through so the wrapped app's own lifecycle still runs.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Awaitable, Callable, Iterable, MutableMapping
from typing import TYPE_CHECKING, Generic, Protocol, TypeVar, cast

if TYPE_CHECKING:
    from pathlib import Path

Scope = MutableMapping[str, object]
Receive = Callable[[], Awaitable[MutableMapping[str, object]]]
Send = Callable[[MutableMapping[str, object]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

_P = TypeVar("_P")
_TOKEN_BYTES = 32


class TokenGate:
    """ASGI middleware: pass an HTTP request only when its ``header`` token ``accepts``."""

    def __init__(
        self, app: ASGIApp, *, header: str, accepts: Callable[[str], bool], deny_message: str = "missing or invalid token"
    ) -> None:
        self._app = app
        self._header = header.lower().encode()
        self._accepts = accepts
        self._deny_body = json.dumps({"error": deny_message}).encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        token = self._token(scope)
        if token is None or not self._accepts(token):
            await self._deny(send)
            return
        await self._app(scope, receive, send)

    def _token(self, scope: Scope) -> str | None:
        raw_headers = cast("Iterable[tuple[bytes, bytes]]", scope.get("headers") or ())
        raw = dict(raw_headers).get(self._header)
        if not isinstance(raw, bytes):
            return None
        try:
            return raw.decode()
        except UnicodeDecodeError:
            return None

    async def _deny(self, send: Send) -> None:
        await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": self._deny_body})


class StaticTokenGate(TokenGate):
    """A :class:`TokenGate` over one static secret, compared in constant time."""

    def __init__(self, app: ASGIApp, token: str, *, header: str, deny_message: str = "missing or invalid token") -> None:
        if not token:
            msg = "a static token gate needs a non-empty token"
            raise ValueError(msg)
        super().__init__(app, header=header, accepts=lambda given: secrets.compare_digest(given, token), deny_message=deny_message)


class LeaseSet(Generic[_P]):
    """An in-memory ``token -> holder`` set with mint / revoke / resolve. Never serialized."""

    def __init__(self) -> None:
        self._leases: dict[str, _P] = {}

    def mint(self, holder: _P) -> str:
        """A fresh unguessable token (``secrets.token_urlsafe(32)``) that resolves to ``holder``."""
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        self._leases[token] = holder
        return token

    def revoke(self, token: str) -> None:
        """Drop ``token`` (idempotent). Effective on the next request."""
        self._leases.pop(token, None)

    def resolve(self, token: str) -> _P | None:
        """The holder of ``token``, or ``None`` when unknown or revoked.

        A constant-time scan, not ``dict.get``: a dict lookup short-circuits on the first
        differing byte, so its timing leaks a prefix. The set is small (one per live lease).
        """
        found: _P | None = None
        for known, holder in self._leases.items():
            if secrets.compare_digest(known, token):
                found = holder
        return found

    def __len__(self) -> int:
        return len(self._leases)


class Resolver(Protocol):
    """Anything that resolves a token to its holder, ``None`` when it is not live: a :class:`LeaseSet`."""

    def resolve(self, token: str, /) -> object | None: ...


class LeaseTokenGate(TokenGate):
    """A :class:`TokenGate` that passes a token only while ``leases`` resolves it."""

    def __init__(self, app: ASGIApp, leases: Resolver, *, header: str, deny_message: str = "missing or invalid lease token") -> None:
        super().__init__(app, header=header, accepts=lambda given: leases.resolve(given) is not None, deny_message=deny_message)


def stable_token(path: Path) -> str:
    """The token stored at ``path``; minted into a new ``0600`` file when there is none."""
    if path.exists():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600, exist_ok=True)  # 0600 before the secret is written: never world-readable
    path.chmod(0o600)
    path.write_text(token, encoding="utf-8")
    return token


__all__ = ["ASGIApp", "LeaseSet", "LeaseTokenGate", "Receive", "Resolver", "Scope", "Send", "StaticTokenGate", "TokenGate", "stable_token"]
