"""Scoped filters for the two known transport teardown log records."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, override

from anyio import ClosedResourceError

if TYPE_CHECKING:
    from collections.abc import Generator


class SseWriterNoiseFilter(logging.Filter):
    """Drop only the known close-race messages with an actual closed-resource cause."""

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        exc = record.exc_info[1] if record.exc_info else None
        return not (
            record.getMessage() in {"Error in standalone SSE writer", "Error handling POST request"}
            and isinstance(exc, ClosedResourceError)
        )


class LifespanCancelNoiseFilter(logging.Filter):
    """Drop uvicorn's textual traceback only when it ends in lifespan cancellation."""

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not (message.startswith("Traceback") and message.rstrip().endswith("CancelledError"))


@contextlib.contextmanager
def teardown_logs() -> Generator[None]:
    """Install filters for this serving lifetime, restoring both loggers on exit."""
    filters = [
        (logging.getLogger("mcp.server.streamable_http"), SseWriterNoiseFilter()),
        (logging.getLogger("uvicorn.error"), LifespanCancelNoiseFilter()),
    ]
    for logger, noise_filter in filters:
        logger.addFilter(noise_filter)
    try:
        yield
    finally:
        for logger, noise_filter in filters:
            logger.removeFilter(noise_filter)
