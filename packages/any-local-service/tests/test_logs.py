"""Only the two known teardown records disappear; other errors remain visible."""

from __future__ import annotations

import logging

import pytest
from any_local_service.logs import teardown_logs
from anyio import ClosedResourceError


@pytest.mark.parametrize(
    "message,error,hidden",
    [
        ("Error in standalone SSE writer", ClosedResourceError(), True),
        ("Error handling POST request", ClosedResourceError(), True),
        ("Error in standalone SSE writer", ValueError(), False),
        ("real error", ClosedResourceError(), False),
    ],
)
def test_stream_filter_is_precise_and_removed_after_lifetime(caplog, message, error, hidden):
    logger = logging.getLogger("mcp.server.streamable_http")
    before = list(logger.filters)
    with teardown_logs():
        logger.error(message, exc_info=(type(error), error, None))
    assert (message not in caplog.text) == hidden
    assert logger.filters == before


def test_lifespan_cancel_filter_keeps_other_tracebacks(caplog, monkeypatch):
    logger = logging.getLogger("uvicorn.error")
    monkeypatch.setattr(logger, "handlers", [caplog.handler])
    before = list(logger.filters)
    with teardown_logs():
        logger.error("Traceback (most recent call last):\nasyncio.exceptions.CancelledError")
        logger.error("Traceback (most recent call last):\nValueError")
    assert "CancelledError" not in caplog.text
    assert "ValueError" in caplog.text
    assert logger.filters == before
