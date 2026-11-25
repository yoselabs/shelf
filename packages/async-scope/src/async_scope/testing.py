"""A pytest fixture for suites that talk to an MCP server served in-process (``async_scope.asgi``).

The mcp SDK (1.28.1) streamable-HTTP server hands the read end of a per-request memory stream to
``EventSourceResponse`` and never closes it, so each SSE reply leaks one ``MemoryObjectReceiveStream``.
Under ``filterwarnings = error`` the leak surfaces as an unraisable ``ResourceWarning`` at an arbitrary
garbage collection. The leak is upstream, not this package's: a plain uvicorn server and a plain
fastmcp ``Client`` leak the same way (``docs/research/mcp-stream-leak.md``).

Import the fixture into a package's ``conftest.py`` and it applies to that package's tests::

    from async_scope.testing import close_leaked_memory_streams  # noqa: F401

pytest is imported here, and anyio only when the fixture runs, so install ``async-scope[testing]``
beside whatever brings anyio (the mcp SDK does). Delete this module when the upstream fix lands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = ["close_leaked_memory_streams"]


@pytest.fixture(autouse=True)
def close_leaked_memory_streams(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Hold every anyio memory receive stream a test creates, then close it at teardown."""
    from anyio.streams.memory import MemoryObjectReceiveStream  # noqa: PLC0415 — only the suites that use the fixture have anyio

    held: list[MemoryObjectReceiveStream[Any]] = []
    original = MemoryObjectReceiveStream.__init__

    def tracked(self: MemoryObjectReceiveStream[Any], *args: Any, **kwargs: Any) -> None:
        original(self, *args, **kwargs)
        held.append(self)

    monkeypatch.setattr(MemoryObjectReceiveStream, "__init__", tracked)
    yield
    for stream in held:
        stream.close()
