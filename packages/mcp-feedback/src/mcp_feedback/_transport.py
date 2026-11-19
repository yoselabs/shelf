"""OTLP/HTTP-logs POST transport — best-effort, never raises.

Not the OTel Logs SDK: that API is marked unstable/private in the Python SDK
(`opentelemetry.sdk._logs`, underscore-prefixed) and its exporter is
synchronous (`requests`-based) — no proven benefit over a hand-rolled async
POST in an async-native caller.
"""

from __future__ import annotations

import logging

import httpx

_log = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5.0


async def post_feedback_logs(
    *,
    endpoint: str,
    api_key: str,
    scope_name: str,
    resource_attrs: list[dict[str, object]],
    log_records: list[dict[str, object]],
) -> bool:
    """POST one OTLP/HTTP logs payload.

    No-op unless both `endpoint` and `api_key` are configured. Never
    raises — a dead or misconfigured endpoint must never surface as a
    caller-visible failure.

    Returns whether a send was ATTEMPTED (`endpoint` + `api_key` both
    present) — never whether it was actually delivered, which is invisible
    by design (best-effort, swallowed on failure).
    """
    if not endpoint or not api_key:
        return False
    payload = {
        "resourceLogs": [
            {
                "resource": {"attributes": resource_attrs},
                "scopeLogs": [{"scope": {"name": scope_name}, "logRecords": log_records}],
            }
        ]
    }
    try:
        # Redirects are refused (a redirect would carry the API key to another host) and the reply is
        # never read: `stream` returns at the headers, so an unbounded body is never pulled into memory.
        async with (
            httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, follow_redirects=False) as client,
            client.stream("POST", endpoint, json=payload, headers={"X-Api-Key": api_key}),
        ):
            pass
    except (httpx.HTTPError, OSError) as exc:  # best-effort — never break the caller
        _log.warning("mcp_feedback_report_failed", extra={"error": str(exc)})
    return True
