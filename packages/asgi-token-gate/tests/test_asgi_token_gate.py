"""One token gate, two ways to know a token (moved from a2kay tests/core/test_leases.py,
tests/test_spoke_auth.py and tests/test_server_token.py)."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import httpx
import pytest
from asgi_token_gate import LeaseSet, LeaseTokenGate, StaticTokenGate, TokenGate, stable_token

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from pathlib import Path

    from asgi_token_gate import ASGIApp, Receive, Scope, Send

_HEADER = "X-Test-Token"


class _Recorder:
    """A trivial ASGI app that records whether it was reached."""

    def __init__(self) -> None:
        self.reached = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        del scope, receive
        self.reached = True
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


def _request(app: ASGIApp, headers: dict[str, str]) -> httpx.Response:
    async def _call() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://gate") as client:
            return await client.post("/mcp/", headers=headers, json={})

    return asyncio.run(_call())


async def _drive(app: ASGIApp, scope: Scope) -> tuple[int, bytes]:
    """One raw ASGI call: the response status and body."""
    status = {"code": 0}
    bodies: list[bytes] = []

    async def receive() -> MutableMapping[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg: MutableMapping[str, object]) -> None:
        if msg["type"] == "http.response.start":
            status["code"] = int(str(msg["status"]))
        elif msg["type"] == "http.response.body":
            body = msg["body"]
            assert isinstance(body, bytes)
            bodies.append(body)

    await app(scope, receive, send)
    return status["code"], b"".join(bodies)


# --- the lease set ---------------------------------------------------------------------


def test_a_minted_lease_resolves_to_its_holder() -> None:
    leases: LeaseSet[str] = LeaseSet()
    token = leases.mint("job:transcribe")
    assert leases.resolve(token) == "job:transcribe"
    assert len(leases) == 1


def test_revoke_makes_the_next_call_fail_and_is_idempotent() -> None:
    leases: LeaseSet[str] = LeaseSet()
    token = leases.mint("job:x")
    leases.revoke(token)
    leases.revoke(token)
    assert leases.resolve(token) is None


def test_a_held_token_never_expires() -> None:
    leases: LeaseSet[str] = LeaseSet()
    token = leases.mint("job:long")
    assert all(leases.resolve(token) == "job:long" for _ in range(1000))


def test_tokens_are_unique_and_unguessable() -> None:
    leases: LeaseSet[int] = LeaseSet()
    tokens = {leases.mint(i) for i in range(50)}
    assert len(tokens) == 50
    assert all(len(t) >= 32 for t in tokens)


def test_the_set_holds_no_filesystem_state(tmp_path: Path) -> None:
    leases: LeaseSet[str] = LeaseSet()
    before = set(tmp_path.rglob("*"))
    leases.revoke(leases.mint("job:x"))
    assert set(tmp_path.rglob("*")) == before


def test_only_the_exact_token_resolves() -> None:
    leases: LeaseSet[str] = LeaseSet()
    token = leases.mint("job:x")
    assert leases.resolve(token[:-1] + ("a" if token[-1] != "a" else "b")) is None
    assert leases.resolve("") is None
    assert leases.resolve(token + "x") is None, "a valid prefix is not a valid token"
    assert leases.resolve("never-minted") is None


def test_the_right_lease_among_several() -> None:
    leases: LeaseSet[str] = LeaseSet()
    first = leases.mint("job:first")
    second = leases.mint("job:second")
    assert leases.resolve(second) == "job:second"
    leases.revoke(second)
    assert leases.resolve(second) is None
    assert leases.resolve(first) == "job:first", "revoking one lease must not disturb another"


# --- the lease gate --------------------------------------------------------------------


def test_lease_gate_refuses_a_missing_token() -> None:
    inner = _Recorder()
    assert _request(LeaseTokenGate(inner, LeaseSet[str](), header=_HEADER), {}).status_code == 401
    assert not inner.reached


def test_lease_gate_passes_a_live_lease() -> None:
    leases: LeaseSet[str] = LeaseSet()
    token = leases.mint("job:x")
    assert _request(LeaseTokenGate(_Recorder(), leases, header=_HEADER), {_HEADER: token}).status_code == 200


def test_lease_gate_refuses_a_revoked_lease() -> None:
    leases: LeaseSet[str] = LeaseSet()
    token = leases.mint("job:x")
    leases.revoke(token)
    response = _request(LeaseTokenGate(_Recorder(), leases, header=_HEADER), {_HEADER: token})
    assert response.status_code == 401
    assert response.json() == {"error": "missing or invalid lease token"}


def test_lease_gate_refuses_an_unknown_token() -> None:
    response = _request(LeaseTokenGate(_Recorder(), LeaseSet[str](), header=_HEADER), {_HEADER: "not-a-real-token"})
    assert response.status_code == 401


# --- the static gate -------------------------------------------------------------------


def test_static_gate_passes_the_token_and_refuses_otherwise() -> None:
    header = _HEADER.lower().encode()
    for given, status, reached in ((b"s3cret", 200, True), (b"wrong", 401, False), (b"\xff\xfe", 401, False)):
        inner = _Recorder()
        gate = StaticTokenGate(inner, "s3cret", header=_HEADER)
        assert asyncio.run(_drive(gate, {"type": "http", "headers": [(header, given)]}))[0] == status
        assert inner.reached is reached
    inner = _Recorder()
    assert asyncio.run(_drive(StaticTokenGate(inner, "s3cret", header=_HEADER), {"type": "http", "headers": []}))[0] == 401
    assert not inner.reached


def test_a_static_gate_needs_a_token() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        StaticTokenGate(_Recorder(), "", header=_HEADER)


def test_a_lifespan_scope_passes_through() -> None:
    inner = _Recorder()
    gate = StaticTokenGate(inner, "s3cret", header=_HEADER)
    asyncio.run(_drive(gate, {"type": "lifespan"}))
    assert inner.reached


def test_the_deny_body_is_json_with_the_message() -> None:
    gate = TokenGate(_Recorder(), header=_HEADER, accepts=lambda _t: False, deny_message="go away")
    status, body = asyncio.run(_drive(gate, {"type": "http", "headers": []}))
    assert status == 401
    assert json.loads(body) == {"error": "go away"}


# --- the stable token ------------------------------------------------------------------


def test_the_token_is_minted_once_and_stable(tmp_path: Path) -> None:
    path = tmp_path / "derived" / "agent.token"
    first = stable_token(path)
    assert first
    assert stable_token(path) == first


def test_the_token_file_is_0600(tmp_path: Path) -> None:
    path = tmp_path / "agent.token"
    stable_token(path)
    assert (path.stat().st_mode & 0o777) == 0o600


def test_an_empty_token_file_is_minted_over(tmp_path: Path) -> None:
    path = tmp_path / "agent.token"
    path.write_text("  \n", encoding="utf-8")
    token = stable_token(path)
    assert token
    assert path.read_text(encoding="utf-8") == token
