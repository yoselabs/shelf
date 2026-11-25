"""The in-process MCP server leaks one memory receive stream per SSE reply (upstream); the shared fixture closes them."""

from async_scope.testing import close_leaked_memory_streams  # noqa: F401 — an autouse fixture, registered by import
