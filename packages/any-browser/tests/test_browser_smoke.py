"""Opt-in real-browser smoke check — launches the actual browser binaries.

This is the "real check" the otherwise all-fake backend suite lacks: it proves
each engine launches, executes JavaScript, and returns rendered HTML — the
regression class ("the engine can't launch on this version") that no fake can
catch. Both families are covered:

  - Playwright API → patchright (fast Chromium)
  - raw CDP        → zendriver

Excluded from the default `make check` run (the `browser` marker is deselected
by the pyproject `addopts` default). Run it with `make test-browser`.

**Skip vs fail is environment-conditional (the dead-rung guard).** On a dev
laptop with no Chromium, a missing engine skips — humane and correct for the
inner loop. But a skip in the one environment you *control* is a dead rung
wearing a green coat: that is precisely how a robust rung that could not launch
AT ALL (zendriver `--no-sandbox` via a config API that rejects it) stayed green
through a full release gate. So the browser CI lane sets `SHELF_REQUIRE_BROWSER=1`
after installing Chromium, and in that lane a non-launching engine is a hard
FAILURE, not a skip.
"""

from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING

import pytest
from any_browser import PlaywrightBackend, RenderedPage, RenderOutcome, ZendriverBackend, patchright_launcher

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.browser


def _require_browser() -> bool:
    """True when a real launch is obligated (the CI browser lane sets the flag).

    Read at call time, not import time, so the policy can be exercised
    deterministically without reimporting this module.
    """
    return os.environ.get("SHELF_REQUIRE_BROWSER", "").strip().lower() in ("1", "true", "yes")


def browser_unavailable_policy(reason: str, *, required: bool) -> None:
    """The skip→fail decision, pure and testable (no env, no browser).

    Skip on a dev machine; FAIL where a real launch is obligated. Kept pure and
    exported so `test_browser_gate_policy.py` can pin the FAIL branch — the
    branch a working browser can never exercise, and exactly the one that stayed
    silently correct-looking while a dead rung shipped.
    """
    if required:
        pytest.fail(f"SHELF_REQUIRE_BROWSER is set but the engine did not launch: {reason}")  # ty: ignore[invalid-argument-type]
    pytest.skip(reason)  # ty: ignore[too-many-positional-arguments]


def _browser_unavailable(reason: str) -> None:
    """The chokepoint every smoke routes its "engine didn't come up" outcome
    through, so the policy lives in one place and cannot drift per-test."""
    browser_unavailable_policy(reason, required=_require_browser())


# A page whose visible content exists ONLY after JavaScript runs — the raw HTML
# body is a single "loading" placeholder, so non-empty rendered HTML carrying the
# injected sentinel proves the engine actually executed the script.
_JS_PAGE = """<!doctype html>
<html><head><title>Browser Smoke</title></head>
<body>
<div id="app">loading…</div>
<script>
  document.getElementById('app').innerHTML =
    '<article><h1>Browser Smoke OK</h1>' +
    '<p>' + 'The browser rendered this paragraph after executing JavaScript. '.repeat(8) + '</p>' +
    '</article>';
</script>
</body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = _JS_PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — matches BaseHTTPRequestHandler's own parameter name
        return  # silence the dev server


@pytest.fixture
def js_fixture_url() -> Iterator[str]:
    """Serve the JS-rendering page from a throwaway localhost server."""
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address  # ty: ignore[invalid-assignment]
    try:
        yield f"http://{host}:{port}/"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _assert_rendered_js(page: RenderedPage) -> None:
    """Assert a RenderedPage proves JS ran (the sentinel is injected by script)."""
    assert page.outcome is RenderOutcome.ok, page.detail
    assert page.js_executed is True
    assert "Browser Smoke OK" in page.html


async def test_patchright_playwright_family_executes_js(js_fixture_url: str) -> None:
    """Playwright-API family: real patchright Chromium executes JS."""
    try:
        import patchright.async_api  # noqa: F401, PLC0415  # ty: ignore[unresolved-import] — presence probe: skip if the engine is absent
    except ImportError as exc:
        _browser_unavailable(f"patchright not installed: {exc}")

    backend = PlaywrightBackend(patchright_launcher, name="patchright")
    try:
        await backend._ensure()
    except Exception as exc:  # noqa: BLE001 — binary missing / launch failed is an environment condition, not a bug: skip or fail per policy
        await backend.close()
        _browser_unavailable(f"patchright Chromium unavailable: {exc!r}")
    try:
        page = await backend.render(js_fixture_url, cookies=[], budget_s=20.0, js_heavy=True)
        _assert_rendered_js(page)
    finally:
        await backend.close()


async def test_zendriver_cdp_family_executes_js(js_fixture_url: str) -> None:
    """Raw-CDP family: real zendriver executes JS."""
    try:
        import zendriver  # noqa: F401, PLC0415 — presence probe: skip the smoke if the engine isn't installed
    except ImportError as exc:
        _browser_unavailable(f"zendriver not installed: {exc}")

    backend = ZendriverBackend(name="zendriver")
    # zendriver launches per-render; a launch failure surfaces as
    # RenderOutcome.unavailable — skip on that (dev machine), fail if obligated.
    page = await backend.render(js_fixture_url, cookies=[], budget_s=20.0, js_heavy=True)
    if page.outcome is RenderOutcome.unavailable:
        _browser_unavailable(f"zendriver Chromium unavailable: {page.detail}")
    _assert_rendered_js(page)
