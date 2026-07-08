"""browser-cookie3 adapter — single dispatch for all supported browsers.

browser-cookie3 owns the per-browser file paths, decryption (Chrome AES-GCM via
pycryptodomex + Keychain on macOS), and the OS matrix (macOS / Linux / Windows).
This module narrows it to a typed boundary: a `CookieSource` literal →
`list[CookieRow]`.

The `browser-cookie3` dependency is OPTIONAL and imported LAZILY inside
`_dispatch`. The package therefore imports fine without it; the lib is only
needed at call time, and its absence degrades to a `CookieAccessError` with an
actionable "install browser-cookies[read]" message.

Per-browser `profile` resolution defers to browser-cookie3 defaults. A non-default
`profile` value is currently a hint only — browser-cookie3 does not expose
per-profile selection uniformly across browsers; expand here when a concrete need
arrives.

NEVER include cookie values, AES keys, or Keychain material in raised exception
messages. `CookieAccessError` carries structural context only (browser name,
exception class). `__cause__` preserves the original.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from .models import ChromeCookieAccessError, CookieAccessError, CookieRow, SameSite

if TYPE_CHECKING:
    from collections.abc import Callable
    from http.cookiejar import Cookie, CookieJar

CookieSource = Literal[
    "chrome",
    "chromium",
    "brave",
    "edge",
    "firefox",
    "safari",
    "vivaldi",
    "opera",
    "opera_gx",
]


def _dispatch(source: CookieSource) -> Callable[..., CookieJar]:
    """Resolve a `CookieSource` to its browser-cookie3 reader function.

    Raises:
        CookieAccessError: When the optional `browser-cookie3` extra is absent,
            or when `source` is not a supported browser.
    """
    try:
        import browser_cookie3 as bc3  # noqa: PLC0415  # lazy on purpose: optional [read] engine, imported at call time so the package imports without it
    except ModuleNotFoundError as err:
        # The deferred import lets a slim/server install omit `browser-cookie3`
        # entirely; when a caller nonetheless tries to read a real browser,
        # degrade to CookieAccessError (a consumer catches it → loud note, no
        # crash).
        msg = "reading browser cookies needs the [read] extra — install browser-cookies[read] (a local-only feature)"
        raise CookieAccessError(msg) from err

    table: dict[str, Callable[..., CookieJar]] = {
        "chrome": bc3.chrome,
        "chromium": bc3.chromium,
        "brave": bc3.brave,
        "edge": bc3.edge,
        "firefox": bc3.firefox,
        "safari": bc3.safari,
        "vivaldi": bc3.vivaldi,
        "opera": bc3.opera,
        "opera_gx": bc3.opera_gx,
    }
    try:
        return table[source]
    except KeyError as err:
        msg = f"Unsupported cookie source: {source!r}"
        raise CookieAccessError(msg) from err


def _samesite(cookie: Cookie) -> SameSite:
    raw = cookie.get_nonstandard_attr("SameSite") or cookie.get_nonstandard_attr("samesite")
    if raw is None:
        return None
    s = str(raw).lower()
    if s == "lax":
        return "lax"
    if s == "strict":
        return "strict"
    if s == "none":
        return "none"
    return None


def _to_row(cookie: Cookie) -> CookieRow:
    # `http.cookiejar.Cookie.domain` is the on-disk host_key shape: either bare
    # host or leading-dot domain-match form. Pass through unchanged.
    expires = int(cookie.expires) if cookie.expires else None
    is_secure = 1 if cookie.secure else 0
    is_httponly = 1 if cookie.has_nonstandard_attr("HttpOnly") else 0
    return CookieRow(
        host_key=cookie.domain or "",
        name=cookie.name or "",
        value=cookie.value or "",
        path=cookie.path or "/",
        expires_utc=expires,
        is_secure=is_secure,
        is_httponly=is_httponly,
        samesite=_samesite(cookie),
    )


def read_cookies(
    source: CookieSource,
    profile: str | None = None,  # noqa: ARG001  # reserved for a future per-browser profile-file resolver
    domain: str | None = None,
) -> list[CookieRow]:
    """Read all cookies from the given browser's default profile.

    Args:
        source: The browser to read from.
        profile: Currently unused (reserved for a future per-browser
            profile-file resolver); browser-cookie3 selects the system default.
        domain: Narrows extraction at the source when provided.

    Returns:
        The browser's cookies as normalized `CookieRow` values.

    Raises:
        CookieAccessError: When the store cannot be read or decrypted, when the
            optional extra is absent, or when `source` is unsupported.
    """
    fn = _dispatch(source)
    try:
        jar: CookieJar = fn(domain_name=domain or "")
    except CookieAccessError:
        raise
    except Exception as err:
        msg = f"Failed to read {source} cookies ({type(err).__name__})"
        raise CookieAccessError(msg) from err
    return [_to_row(c) for c in jar]


__all__ = ("ChromeCookieAccessError", "CookieAccessError", "CookieSource", "read_cookies")
