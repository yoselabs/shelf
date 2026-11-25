"""The in-process FastMCP server leaks a receive stream per SSE reply (mcp SDK `_handle_post_request` never closes its reader).

Each test holds every memory receive stream it creates until teardown, then closes it, so the leak is released by the test
instead of surfacing as an unraisable ResourceWarning at an arbitrary garbage collection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from anyio.streams.memory import MemoryObjectReceiveStream

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _close_leaked_memory_streams(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    held: list[MemoryObjectReceiveStream[Any]] = []
    original = MemoryObjectReceiveStream.__init__

    def tracked(self: MemoryObjectReceiveStream[Any], *args: Any, **kwargs: Any) -> None:
        original(self, *args, **kwargs)
        held.append(self)

    monkeypatch.setattr(MemoryObjectReceiveStream, "__init__", tracked)
    yield
    for stream in held:
        stream.close()
