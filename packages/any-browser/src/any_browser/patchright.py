"""Patchright launcher — Chromium Playwright drop-in, the FAST rung.

Patchright is an undetected Playwright fork that vendors its own
playwright-core and browser binary; only the launch differs from Camoufox, so
it reuses :class:`PlaywrightBackend` wholesale via a ``launch_fn``. Ship it in
an optional extra (the baked Chromium dominates image size).
"""

from __future__ import annotations

from typing import Any

from .playwright import chromium_launch


def patchright_launcher() -> Any:
    """Yield an async-CM launching headless Chromium via Patchright.

    ``ImportError`` (the ``patchright`` engine is not installed) propagates →
    the backend reports ``unavailable``.
    """
    # lazy: patchright is the optional [patchright] extra.
    from patchright.async_api import async_playwright  # noqa: PLC0415  # ty: ignore[unresolved-import]

    return chromium_launch(async_playwright)
