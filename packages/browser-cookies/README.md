# browser-cookies

**Read the local machine's browser cookies as typed rows.** A thin, cross-platform
adapter over [`browser-cookie3`](https://github.com/borisbabic/browser_cookie3):
one `CookieSource` literal in, a `list[CookieRow]` out. browser-cookie3 owns the
per-browser file paths, decryption (Chrome AES-GCM + Keychain on macOS), and the
OS matrix (macOS / Linux / Windows); this package narrows it to a stable, typed
boundary and a single error type.

```python
from browser_cookies import read_cookies, CookieAccessError

try:
    rows = read_cookies("chrome", domain="example.com")
except CookieAccessError as err:
    ...  # loud, structural — never leaks cookie values or key material
```

- **Multi-browser** — Chrome / Chromium / Brave / Edge / Firefox / Safari /
  Vivaldi / Opera / Opera GX.
- **Optional, lazy engine** — `browser-cookie3` is the `[read]` extra and is
  imported *inside* the call. The package imports fine without it; a slim/server
  install can omit it entirely and every `read_cookies` call degrades to a loud
  `CookieAccessError` ("install browser-cookies[read]") instead of crashing at
  import time.
- **Secret-safe errors** — raised messages carry only the browser name and the
  upstream exception class; `__cause__` preserves the original.

## Install

```bash
pip install "browser-cookies[read]"   # includes the browser-cookie3 reader
pip install browser-cookies            # import-only; reads raise until [read] is present
```

## Boundary type

`CookieRow` is a frozen, slotted dataclass with the on-disk sqlite shape
normalized across browsers: `host_key`, `name`, `value`, `path`,
`expires_utc` (unix seconds, `None` = session), `is_secure`/`is_httponly`
(0/1 ints), and a normalized `samesite` (`"lax"|"strict"|"none"|None`).
