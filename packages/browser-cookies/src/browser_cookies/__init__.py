"""browser-cookies — read the local machine's browser cookie store.

Thin adapter over `browser-cookie3`. Cross-platform (macOS / Linux / Windows)
and multi-browser (Chrome / Chromium / Brave / Edge / Firefox / Safari / Vivaldi
/ Opera / Opera GX). The package owns the boundary types in `.models` and the
dispatch in `.store`; a consumer wires domain conversion at its own seam.

`browser-cookie3` is an OPTIONAL dependency (the `[read]` extra), imported lazily
inside `store._dispatch`. The package imports fine without it; the lib is only
needed at call time and its absence degrades to a `CookieAccessError`.

`ChromeCookieAccessError` is re-exported as a historical alias (subclass) of
`CookieAccessError` for any external caller pinned to the older name.
"""

from __future__ import annotations

from .models import ChromeCookieAccessError, CookieRow
from .store import CookieAccessError, CookieSource, read_cookies

__all__ = (
    "ChromeCookieAccessError",
    "CookieAccessError",
    "CookieRow",
    "CookieSource",
    "read_cookies",
)
