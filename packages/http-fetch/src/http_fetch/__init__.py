"""http-fetch — one HTTP-GET primitive with browser TLS impersonation.

**Stop caring about curl_cffi's session plumbing and exception zoo.** `fetch_bytes`
performs every HTTP GET via :class:`curl_cffi.requests.AsyncSession` with a browser
JA3/JA4 fingerprint, optional proxy / cookies / conditional-GET headers, and an
optional injected circuit breaker. It never raises on a routine failure — every
outcome maps to a :class:`FetchVerdict` on the returned :class:`FetchOutcome`.

Domain-independent: the routing / stealth / retry *policy* lives above this primitive
and passes into it (``proxy_url``, ``breaker``, ``impersonate``); nothing here reaches
back out.
"""

from __future__ import annotations

from .fetch import conditional_headers, fetch_bytes
from .models import FetchOutcome, FetchVerdict

__all__ = ("FetchOutcome", "FetchVerdict", "conditional_headers", "fetch_bytes")
