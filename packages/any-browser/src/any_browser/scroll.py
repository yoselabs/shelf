"""The thin-page scroll retry of the Playwright backend: one scroll, one networkidle wait, one re-snapshot."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import logging


async def scroll_and_retry(page: Any, original_html: str, *, log: logging.Logger) -> str:  # Any: a Playwright Page, optional dependency
    """Scroll-to-bottom + 2s networkidle wait + re-snapshot.

    Returns whichever capture (original or post-scroll) is longer. Never
    raises. Emits ``browser_scroll_retry`` diagnostics on the injected logger
    (typed-record shape: message = event name, payload on ``fields``) so
    consumers measure firing rate without coupling this package to their event
    types.
    """
    log.info("StageStarted", extra={"fields": {"t_ms": 0, "step": "browser_scroll_retry"}})
    start = time.perf_counter()
    larger = original_html
    outcome = "smaller"
    try:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        try:
            await page.wait_for_load_state("networkidle", timeout=2_000)
        except Exception:
            # networkidle never settled — try a brief sleep then snapshot anyway
            await asyncio.sleep(0.5)
        retry_html = await page.content()
        if len(retry_html) > len(original_html):
            larger = retry_html
            outcome = "larger"
    except Exception:
        outcome = "timeout"
    dur_ms = int((time.perf_counter() - start) * 1000)
    fields = {"t_ms": 0, "step": "browser_scroll_retry", "verdict": "ok", "dur_ms": dur_ms, "extra": {"outcome": outcome}}
    log.info("StageEnded", extra={"fields": fields})
    return larger
