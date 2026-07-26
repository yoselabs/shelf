"""Stop caring which browser engine renders a JS page.

``any_browser`` is the "any-*" seam for headless rendering: a consumer says
"render this URL with cookies, within this budget" and stays blind to whether a
Playwright-API engine (Camoufox, Patchright) or a raw-CDP engine (zendriver)
is underneath. The interface (:class:`BrowserBackend`) and its value objects
(:class:`RenderedPage`, :class:`BackendCookie`, :class:`RenderOutcome`) carry no
consumer types, so the same backend drops into any app.

Two engine families prove the seam spans more than one driver API:

- :class:`PlaywrightBackend` — the Playwright-API family (per-host LRU context
  pool, idle reaper, driver-stderr capture), launched via a ``launch_fn``
  (:func:`patchright_launcher`, :func:`camoufox_launcher`, or
  :func:`chromium_launch` over any Playwright drop-in).
- :class:`ZendriverBackend` — a browser driven directly over CDP, per-render
  launch, for the SPAs a Playwright drop-in fails to read.

The engines themselves are optional dependencies (install the ``playwright`` or
``cdp`` extra); a missing engine surfaces as ``RenderOutcome.unavailable`` from
``render``, never an import crash — so a consumer can ship the seam and degrade
gracefully when no engine is present.

State-boundary honesty (the any-* design law): ``render`` never raises for a
routine failure — timeout, navigation error, or a missing engine all come back
as a :class:`RenderedPage` with the matching :class:`RenderOutcome`, so the
failure channel is data the consumer maps, not an exception it must guess at.
"""

from __future__ import annotations

from .base import BackendCookie, BrowserBackend, RenderedPage, RenderOutcome
from .patchright import patchright_launcher
from .playwright import PlaywrightBackend, camoufox_launcher, chromium_launch
from .zendriver import ZendriverBackend

__all__ = [
    "BackendCookie",
    "BrowserBackend",
    "PlaywrightBackend",
    "RenderOutcome",
    "RenderedPage",
    "ZendriverBackend",
    "camoufox_launcher",
    "chromium_launch",
    "patchright_launcher",
]
