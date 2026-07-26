"""BrowserBackend Protocol — what every rendering engine implements.

Consumer-free by construction: the interface and its value objects carry no
domain types. A caller converts its own cookie type to :class:`BackendCookie`
before a render and maps :class:`RenderOutcome` / :class:`RenderedPage` to its
own result types afterwards. That keeps this package indifferent to which
engine is underneath *and* to who is calling it — the "stop caring which
browser" seam.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Self, runtime_checkable


class RenderOutcome(StrEnum):
    """The result class of a :meth:`BrowserBackend.render` call — the failure channel.

    ``render`` never raises for a routine failure; it returns a
    :class:`RenderedPage` carrying one of these. The consumer maps them to its
    own outcome vocabulary:

    - ``ok`` — a page was captured.
    - ``timeout`` — navigation or content capture exceeded the budget.
    - ``error`` — an internal navigation/driver error mid-render.
    - ``unavailable`` — the engine is missing or the launch failed.
    """

    ok = "ok"
    timeout = "timeout"
    error = "error"  # internal navigation/driver error mid-render
    unavailable = "unavailable"  # engine missing / launch failed


@dataclass(frozen=True, slots=True)
class BackendCookie:
    """Engine-neutral cookie, converted to each engine's cookie shape by the backend.

    The caller converts its own cookie type to this before a render.
    ``expires=None`` means a session cookie. ``samesite`` is lowercase
    (``"lax" | "strict" | "none" | None``) — the backend titlecases as needed.
    """

    name: str
    value: str
    domain: str
    path: str
    expires: float | None
    secure: bool
    http_only: bool
    samesite: str | None


@dataclass(frozen=True, slots=True)
class RenderedPage:
    """One render result — no consumer types appear here.

    ``detail`` is a one-line message on ``error`` / ``unavailable`` (never a
    multi-line stack — driver stack traces ride the captured-stderr log events).
    """

    outcome: RenderOutcome
    html: str = ""
    final_url: str = ""
    status_code: int = 0
    js_executed: bool = False
    wall_ms: int = 0
    bytes_transferred: int = 0
    detail: str = ""
    # Observation, not conclusion: the count of page subresources (XHR/fetch)
    # that returned a challenge status (401/403/429) during this render. It is a
    # raw signal the render happened to observe — this package attaches no
    # meaning to it. A consumer may read it as evidence (e.g. that a page which
    # rendered a "0 results" shell had its data API blocked), but that
    # interpretation lives entirely in the consumer, not here.
    subresource_blocks: int = 0


@runtime_checkable
class BrowserBackend(Protocol):
    """A JS-capable rendering engine. Implementations live under this package.

    ``render`` MUST NOT raise for routine failures (timeout, navigation error,
    missing engine) — it returns a :class:`RenderedPage` with the corresponding
    ``outcome``. The backend is an async context manager: some engines hold a
    persistent process opened lazily on first render and unwound on exit.
    """

    name: str

    async def render(
        self,
        url: str,
        *,
        cookies: list[BackendCookie],
        budget_s: float,
        js_heavy: bool,
        scroll_to_stable: bool = False,
    ) -> RenderedPage:
        """Render ``url`` and return a :class:`RenderedPage` (never raise for a routine failure)."""
        ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None: ...
