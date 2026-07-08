"""Boundary types for the browser-cookies package.

Package-owned types — no imports from a consumer app. A consumer wires its own
`Cookie` shape and converts from `CookieRow` at the seam.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SameSite = Literal["lax", "strict", "none"] | None


@dataclass(slots=True, frozen=True)
class CookieRow:
    """One cookie as returned by the per-browser reader.

    Storage shape is normalized across Chrome and Firefox. Consumer code
    converts to its own `Cookie` shape when bridging into its cookie jar.

    Attributes:
        host_key: Chrome-style — either ``example.com`` (host-only) or
            ``.example.com`` (domain match).
        name: Cookie name.
        value: Cookie value.
        path: Cookie path.
        expires_utc: Unix seconds. ``None`` means session cookie (no expiry).
        is_secure: Int (0/1) to match the on-disk sqlite shape.
        is_httponly: Int (0/1) to match the on-disk sqlite shape.
        samesite: Normalized SameSite attribute, or ``None`` when unset/unknown.
    """

    host_key: str
    name: str
    value: str
    path: str
    expires_utc: int | None
    is_secure: int
    is_httponly: int
    samesite: SameSite


class CookieAccessError(RuntimeError):
    """Raised when a browser's cookie store cannot be read or decrypted.

    The message NEVER contains cookie values or key material — only the browser
    name and the upstream exception class. ``__cause__`` is the original
    exception.
    """


# Historical alias (the v0.8 name) — preserved for any external caller pinned to
# it. Kept as a subclass so ``except CookieAccessError`` also catches it.
class ChromeCookieAccessError(CookieAccessError):
    """Historical alias of :class:`CookieAccessError` (the v0.8 name).

    Covers missing profile dir, missing sqlite file, Keychain access denied,
    ``security`` CLI failures, decryption errors. The message NEVER contains
    decrypted cookie values or the AES key — only structural context.
    """


__all__ = ("ChromeCookieAccessError", "CookieAccessError", "CookieRow", "SameSite")
